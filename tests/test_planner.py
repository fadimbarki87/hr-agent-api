import copy
import unittest

from hr_agent.planner import PLAN_AUDIT_SYSTEM_PROMPT, plan_question


def aggregate_plan(alias):
    return {
        "supported": True,
        "unsupported_category": "none",
        "route": "sql_only",
        "answer_language": "en",
        "semantic_query": "",
        "semantic_scope": "none",
        "query": {
            "base_table": "employees",
            "select": [
                {
                    "field": "employees.salary",
                    "aggregate": "avg",
                    "distinct": False,
                    "alias": alias,
                }
            ],
            "filters": [],
            "group_by": [],
            "order_by": [],
            "limit": None,
        },
    }


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def chat_json(self, system_prompt, user_prompt, *, max_tokens):
        self.calls += 1
        if system_prompt == PLAN_AUDIT_SYSTEM_PROMPT:
            return {"valid": True, "issue": "none"}
        return copy.deepcopy(self.responses.pop(0))


class PlannerTests(unittest.TestCase):
    def test_invalid_model_plan_is_retried_before_execution(self):
        client = FakeClient(
            [aggregate_plan(None), aggregate_plan("average_salary")]
        )
        plan = plan_question(client, "What is the average salary?")
        self.assertIsNotNone(plan)
        self.assertEqual("average_salary", plan.query.select[0].alias)
        self.assertEqual(3, client.calls)

    def test_auditor_rejection_triggers_one_bounded_replan(self):
        client = FakeClient(
            [
                aggregate_plan("average_salary"),
                {"valid": False, "issue": "wrong_result_shape"},
                aggregate_plan("average_salary"),
                {"valid": True, "issue": "none"},
            ]
        )

        def unconditionally_pop(system_prompt, user_prompt, *, max_tokens):
            client.calls += 1
            return copy.deepcopy(client.responses.pop(0))

        client.chat_json = unconditionally_pop
        plan = plan_question(client, "What is the average salary?")
        self.assertIsNotNone(plan)
        self.assertEqual(4, client.calls)

    def test_malformed_audit_fails_closed_after_bounded_attempts(self):
        client = FakeClient(
            [
                aggregate_plan("average_salary"),
                {"valid": "yes", "issue": "none"},
                aggregate_plan("average_salary"),
                {"valid": "yes", "issue": "none"},
            ]
        )

        def unconditionally_pop(system_prompt, user_prompt, *, max_tokens):
            client.calls += 1
            return copy.deepcopy(client.responses.pop(0))

        client.chat_json = unconditionally_pop
        self.assertIsNone(plan_question(client, "What is the average salary?"))
        self.assertEqual(4, client.calls)


if __name__ == "__main__":
    unittest.main()
