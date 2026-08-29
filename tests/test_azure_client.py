import json
import unittest

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.settings import Settings


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, url, headers, json, timeout):
        self.calls += 1
        return self.responses.pop(0)


class AzureClientTests(unittest.TestCase):
    def settings(self):
        return Settings(
            "https://example.invalid",
            "chat",
            "embedding",
            "test-version",
            "test-key",
        )

    def test_rate_limit_honors_bounded_retry_after(self):
        success = {
            "choices": [
                {"message": {"content": json.dumps({"route": "sql_only"})}}
            ]
        }
        transport = FakeTransport(
            [
                FakeResponse(429, headers={"retry-after": "20"}),
                FakeResponse(200, success),
            ]
        )
        delays = []
        client = AzureOpenAIClient(
            self.settings(),
            transport=transport,
            sleeper=delays.append,
        )
        result = client.chat_json("system", "user", max_tokens=50)
        self.assertEqual({"route": "sql_only"}, result)
        self.assertEqual([5.0], delays)
        self.assertEqual(2, transport.calls)

    def test_non_retryable_client_error_fails_immediately(self):
        transport = FakeTransport([FakeResponse(400)])
        client = AzureOpenAIClient(
            self.settings(),
            transport=transport,
            sleeper=lambda _delay: self.fail("must not sleep"),
        )
        self.assertIsNone(client.chat_json("system", "user", max_tokens=50))
        self.assertEqual(1, transport.calls)


if __name__ == "__main__":
    unittest.main()
