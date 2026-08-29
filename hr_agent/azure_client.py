from __future__ import annotations

import json as json_module
import time
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import quote

from .settings import Settings


class _UrllibResponse:
    def __init__(self, status_code: int, body: str, headers=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._body = body
        self.headers = headers or {}

    def json(self) -> Any:
        return json_module.loads(self._body)


class UrllibTransport:
    def post(self, url, headers, json, timeout):
        request = urllib.request.Request(
            url,
            data=json_module.dumps(json).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return _UrllibResponse(
                    response.status,
                    response.read().decode("utf-8"),
                    response.headers,
                )
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            return _UrllibResponse(error.code, body or "{}", error.headers)


class AzureOpenAIClient:
    """Small, bounded Azure OpenAI client with dependency injection for tests."""

    EMBEDDING_BATCH_SIZE = 128

    def __init__(self, settings: Settings, transport=None, sleeper=time.sleep):
        self.settings = settings
        self.transport = transport or UrllibTransport()
        self.sleeper = sleeper

    @staticmethod
    def _retry_delay(response) -> float:
        headers = getattr(response, "headers", {}) or {}
        try:
            if headers.get("retry-after-ms"):
                return min(float(headers["retry-after-ms"]) / 1000.0, 5.0)
            if headers.get("retry-after"):
                return min(float(headers["retry-after"]), 5.0)
        except (TypeError, ValueError):
            pass
        return 1.0

    def _deployment_url(self, deployment: str, operation: str) -> str:
        encoded_deployment = quote(deployment, safe="")
        return (
            f"{self.settings.azure_endpoint}/openai/deployments/"
            f"{encoded_deployment}/{operation}?api-version="
            f"{self.settings.api_version}"
        )

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        timeout: int,
    ) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "api-key": self.settings.api_key,
        }

        for attempt in range(2):
            try:
                response = self.transport.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
                if response.ok:
                    body = response.json()
                    return body if isinstance(body, dict) else None
                if self.settings.debug:
                    print("Azure request failed:", response.status_code)
                if response.status_code < 500 and response.status_code != 429:
                    return None
                if attempt == 0:
                    delay = (
                        self._retry_delay(response)
                        if response.status_code == 429
                        else 0.25
                    )
                    self.sleeper(delay)
            except Exception as error:
                if self.settings.debug:
                    print("Azure request exception:", repr(error))

            if self.settings.debug and attempt == 0:
                print("Retrying Azure request once")

        return None

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
    ) -> dict[str, Any] | None:
        if not self.settings.chat_is_configured:
            return None

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        body = self._post_json(
            self._deployment_url(self.settings.chat_deployment, "chat/completions"),
            payload,
            timeout=45,
        )
        if body is None:
            return None

        try:
            content = body["choices"][0]["message"]["content"]
            parsed = json_module.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except (KeyError, IndexError, TypeError, json_module.JSONDecodeError):
            return None

    def chat_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
    ) -> str | None:
        if not self.settings.chat_is_configured:
            return None

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        body = self._post_json(
            self._deployment_url(self.settings.chat_deployment, "chat/completions"),
            payload,
            timeout=45,
        )
        if body is None:
            return None

        try:
            return str(body["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError):
            return None

    def embed_texts(self, texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return []
        if not self.settings.embeddings_are_configured:
            return None

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + self.EMBEDDING_BATCH_SIZE]
            payload = {"input": batch}
            body = self._post_json(
                self._deployment_url(
                    self.settings.embedding_deployment,
                    "embeddings",
                ),
                payload,
                timeout=60,
            )
            if body is None:
                return None

            try:
                entries = sorted(body["data"], key=lambda item: int(item["index"]))
                batch_embeddings = [entry["embedding"] for entry in entries]
                if len(batch_embeddings) != len(batch):
                    return None
                if not all(
                    isinstance(vector, list) and vector
                    for vector in batch_embeddings
                ):
                    return None
                embeddings.extend(batch_embeddings)
            except (KeyError, TypeError, ValueError):
                return None
        return embeddings

    def embed_text(self, text: str) -> list[float] | None:
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else None
