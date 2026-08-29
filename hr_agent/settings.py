from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    azure_endpoint: str
    chat_deployment: str
    embedding_deployment: str
    api_version: str
    api_key: str
    debug: bool = False
    api_access_key: str = ""
    expose_evidence: bool = True
    enable_data_endpoints: bool = True

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
            chat_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
            embedding_deployment=os.getenv(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", ""
            ),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            debug=os.getenv("HR_AGENT_DEBUG", "").lower() in {"1", "true", "yes"},
            api_access_key=os.getenv("HR_AGENT_API_KEY", ""),
            expose_evidence=os.getenv(
                "HR_AGENT_EXPOSE_EVIDENCE", "true"
            ).lower()
            in {"1", "true", "yes"},
            enable_data_endpoints=os.getenv(
                "HR_AGENT_ENABLE_DATA_ENDPOINTS", "true"
            ).lower()
            in {"1", "true", "yes"},
        )

    @property
    def chat_is_configured(self) -> bool:
        return all(
            (
                self.azure_endpoint,
                self.chat_deployment,
                self.api_version,
                self.api_key,
            )
        )

    @property
    def embeddings_are_configured(self) -> bool:
        return self.chat_is_configured and bool(self.embedding_deployment)
