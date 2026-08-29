"""Shared, capped Azure transport for opt-in live evaluation scripts."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from threading import Lock
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def load_private_environment() -> dict[str, str]:
    env_path = ROOT / ".env.test"
    if not env_path.exists():
        return {}
    values = {}
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def configure_private_environment(required: set[str]) -> list[str]:
    environment = load_private_environment()
    missing = sorted(key for key in required if not environment.get(key))
    if missing:
        return missing
    os.environ.update({key: environment[key] for key in required})
    return []


class AzureResponse:
    def __init__(self, status_code: int, body: str, headers=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._body = body
        self.headers = headers or {}

    def json(self):
        return json.loads(self._body)


class AzureUsageTransport:
    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.calls = 0
        self.chat_prompt_tokens = 0
        self.chat_completion_tokens = 0
        self.embedding_tokens = 0
        self.models = set()
        self.status_counts = Counter()
        self.exception_counts = Counter()
        self._lock = Lock()

    def post(self, url, headers, json, timeout):
        with self._lock:
            if self.calls >= self.max_calls:
                raise RuntimeError(f"Azure call limit of {self.max_calls} reached")
            self.calls += 1
        request = urllib.request.Request(
            url,
            data=__import__("json").dumps(json).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                parsed = __import__("json").loads(body)
                usage = parsed.get("usage", {})
                model = parsed.get("model")
                with self._lock:
                    self.status_counts[response.status] += 1
                    if model:
                        self.models.add(str(model))
                    if "/embeddings" in url:
                        self.embedding_tokens += int(usage.get("total_tokens", 0))
                    else:
                        self.chat_prompt_tokens += int(usage.get("prompt_tokens", 0))
                        self.chat_completion_tokens += int(
                            usage.get("completion_tokens", 0)
                        )
                return AzureResponse(response.status, body, response.headers)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            with self._lock:
                self.status_counts[error.code] += 1
            return AzureResponse(error.code, body or "{}", error.headers)
        except Exception as error:
            with self._lock:
                self.exception_counts[type(error).__name__] += 1
            raise

    def usage_summary(self) -> str:
        return (
            f"calls={self.calls}; "
            f"chat_prompt_tokens={self.chat_prompt_tokens}; "
            f"chat_completion_tokens={self.chat_completion_tokens}; "
            f"embedding_tokens={self.embedding_tokens}; "
            f"statuses={dict(sorted(self.status_counts.items()))}; "
            f"exceptions={dict(sorted(self.exception_counts.items()))}; "
            f"models={','.join(sorted(self.models))}"
        )
