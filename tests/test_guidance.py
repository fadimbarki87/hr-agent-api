import json
import unittest

from hr_agent.guidance import (
    AVAILABLE_DATA_SCHEMA,
    formulate_unsupported_guidance,
)


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_json(self, system_prompt, user_prompt, *, max_tokens):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        return self.response


class UnsupportedGuidanceTests(unittest.TestCase):
    def test_grounding_payload_contains_classification_and_schema_not_hr_rows(self):
        client = FakeClient(
            {
                "answer": "Please specify which employee information you need.",
            }
        )
        guidance = formulate_unsupported_guidance(
            client,
            question="Tell me about them.",
            answer_language="en",
            unsupported_category="vague",
        )
        self.assertIsNotNone(guidance)
        payload = json.loads(client.calls[0][1])
        self.assertEqual("vague", payload["unsupported_category"])
        self.assertEqual(AVAILABLE_DATA_SCHEMA, payload["available_data_schema"])
        self.assertNotIn("rows", payload)
        self.assertNotIn("performance_review_text", payload)

    def test_rejects_unknown_category_without_calling_azure(self):
        client = FakeClient(
            {"answer": "Unexpected"}
        )
        self.assertIsNone(
            formulate_unsupported_guidance(
                client,
                question="Question",
                answer_language="en",
                unsupported_category="unknown",
            )
        )
        self.assertEqual([], client.calls)

    def test_rejects_extra_keys_wrong_types_and_oversized_output(self):
        invalid_responses = (
            {"answer": "Text", "extra": "value"},
            {"answer": ["Text"]},
            {"answer": "x" * 901},
        )
        for response in invalid_responses:
            with self.subTest(response=response):
                guidance = formulate_unsupported_guidance(
                    FakeClient(response),
                    question="Question",
                    answer_language="en",
                    unsupported_category="out_of_scope",
                )
                self.assertIsNone(guidance)


if __name__ == "__main__":
    unittest.main()
