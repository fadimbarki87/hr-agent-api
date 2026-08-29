import unittest
from unittest.mock import patch

try:
    from fastapi import HTTPException
    from starlette.requests import Request
except ModuleNotFoundError as error:
    raise unittest.SkipTest(
        "FastAPI runtime dependencies are not installed in this interpreter"
    ) from error

import app as api
from hr_agent.settings import Settings


def request_with_headers(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/ask",
            "headers": encoded_headers,
        }
    )


def settings(**changes) -> Settings:
    values = {
        "azure_endpoint": "https://azure.example",
        "chat_deployment": "chat",
        "embedding_deployment": "embeddings",
        "api_version": "version",
        "api_key": "azure-secret",
    }
    values.update(changes)
    return Settings(**values)


class ApiControlTests(unittest.TestCase):
    def test_access_is_unchanged_when_optional_key_is_not_configured(self):
        with patch.object(api, "RUNTIME_SETTINGS", settings(api_access_key="")):
            self.assertIsNone(api.require_api_access(request_with_headers()))

    def test_access_accepts_bearer_or_api_key_header(self):
        configured = settings(api_access_key="caller-secret")
        with patch.object(api, "RUNTIME_SETTINGS", configured):
            self.assertIsNone(
                api.require_api_access(
                    request_with_headers(
                        {"Authorization": "Bearer caller-secret"}
                    )
                )
            )
            self.assertIsNone(
                api.require_api_access(
                    request_with_headers({"X-API-Key": "caller-secret"})
                )
            )

    def test_access_rejects_invalid_key_without_exposing_expected_value(self):
        configured = settings(api_access_key="caller-secret")
        with patch.object(api, "RUNTIME_SETTINGS", configured):
            with self.assertRaises(HTTPException) as context:
                api.require_api_access(
                    request_with_headers({"X-API-Key": "wrong"})
                )
        self.assertEqual(401, context.exception.status_code)
        self.assertNotIn("caller-secret", str(context.exception.detail))

    def test_data_endpoints_can_be_disabled(self):
        with patch.object(
            api,
            "RUNTIME_SETTINGS",
            settings(enable_data_endpoints=False),
        ):
            with self.assertRaises(HTTPException) as context:
                api.require_data_endpoints()
        self.assertEqual(404, context.exception.status_code)

    def test_readiness_reports_prompt_version_without_secrets(self):
        with patch.object(api, "RUNTIME_SETTINGS", settings()):
            response = api.readiness()
        self.assertEqual("ready", response["status"])
        self.assertEqual(64, len(response["planner_prompt_sha256"]))
        self.assertEqual(64, len(response["plan_audit_prompt_sha256"]))
        self.assertEqual(64, len(response["plan_repair_policy_sha256"]))
        self.assertEqual(64, len(response["rerank_prompt_sha256"]))
        self.assertEqual(
            64,
            len(response["unsupported_guidance_prompt_sha256"]),
        )
        self.assertNotIn("api_key", response)


if __name__ == "__main__":
    unittest.main()
