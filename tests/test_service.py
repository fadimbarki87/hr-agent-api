import unittest

from hr_agent.database import HRDatabase
from hr_agent.planner import PLAN_AUDIT_SYSTEM_PROMPT
from hr_agent.service import HRAgentService, normalize_question_safely
from hr_agent.settings import Settings


def sql_plan(*, language="en", filters=None):
    return {
        "supported": True,
        "unsupported_category": "none",
        "route": "sql_only",
        "answer_language": language,
        "semantic_query": "",
        "semantic_scope": "none",
        "query": {
            "base_table": "employees",
            "select": [
                {
                    "field": "employees.employee_id",
                    "aggregate": None,
                    "distinct": False,
                    "alias": None,
                }
            ],
            "filters": filters or [],
            "group_by": [],
            "order_by": [],
            "limit": None,
        },
    }


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.chat_json_calls = []
        self.chat_text_calls = []

    def chat_json(self, system_prompt, user_prompt, *, max_tokens):
        self.chat_json_calls.append((system_prompt, user_prompt, max_tokens))
        if system_prompt == PLAN_AUDIT_SYSTEM_PROMPT:
            return {"valid": True, "issue": "none"}
        return self.responses.pop(0) if self.responses else None

    def chat_text(self, system_prompt, user_prompt, *, max_tokens):
        self.chat_text_calls.append(user_prompt)
        return None


class FakeRetriever:
    ready = True
    backend = "test"

    def __init__(self, matches):
        self.matches = matches
        self.calls = []

    def search_and_rerank(self, semantic_query, semantic_scope, *, max_results):
        self.calls.append((semantic_query, semantic_scope, max_results))
        return self.matches


def review_match(employee_id, first_name="Alice", department="Engineering"):
    return {
        "employee_id": employee_id,
        "first_name": first_name,
        "last_name": "Example",
        "job_title": "Engineer",
        "department_name": department,
        "performance_review": "Direct supporting evidence.",
        "score": 0.75,
    }


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = HRDatabase.from_project_files()
        cls.settings = Settings("", "", "", "", "")

    def service(self, responses, matches=None):
        return HRAgentService(
            self.settings,
            database=self.database,
            client=FakeClient(responses),
            retriever=FakeRetriever(matches or []),
        )

    def test_safe_normalization_does_not_rewrite_meaning(self):
        cases = [
            "Show the performance review for Anna.",
            "List unpaid vacation.",
            "Show people hired after 2024-01-01.",
            "Who improves team performance?",
        ]
        for question in cases:
            self.assertEqual(question, normalize_question_safely(question))
        self.assertEqual(
            "Hired after 2024-02-01",
            normalize_question_safely("Hired  after 01.02.2024"),
        )

    def test_sql_plan_executes_parameterized_query(self):
        plan = sql_plan(
            filters=[
                {
                    "field": "departments.department_name",
                    "operator": "eq",
                    "value": "Engineering",
                }
            ]
        )
        traced = self.service([plan]).answer_with_trace("Show Engineering IDs")
        evidence = traced["evidence"]
        self.assertEqual("supported", evidence["status"])
        self.assertEqual(8, evidence["result"]["row_count"])
        self.assertEqual(["Engineering"], evidence["sql_parameters"])

    def test_unsupported_plan_is_localized_without_keyword_detection(self):
        plan = {
            "supported": False,
            "unsupported_category": "vague",
            "route": "sql_only",
            "answer_language": "de",
            "semantic_query": "",
            "semantic_scope": "none",
            "query": None,
        }
        traced = self.service([plan]).answer_with_trace("Unbekannte Anfrage")
        self.assertEqual(
            "Nicht unterstützte oder zu vage Frage.",
            traced["answer"],
        )

    def test_semantic_plan_uses_reranked_evidence(self):
        plan = {
            "supported": True,
            "unsupported_category": "none",
            "route": "review_semantic",
            "answer_language": "en",
            "semantic_query": "mentors less experienced colleagues",
            "semantic_scope": "current_strength",
            "query": None,
        }
        retriever = FakeRetriever([review_match(2, "Bob")])
        service = HRAgentService(
            self.settings,
            database=self.database,
            client=FakeClient([plan]),
            retriever=retriever,
        )
        traced = service.answer_with_trace("Who mentors junior colleagues?")
        self.assertEqual("supported", traced["evidence"]["status"])
        self.assertEqual([2], traced["evidence"]["semantic_candidate_ids"])
        self.assertEqual(
            ("mentors less experienced colleagues", "current_strength", 5),
            retriever.calls[0],
        )

    def test_hybrid_plan_injects_reranked_ids_before_structured_filter(self):
        plan = {
            "supported": True,
            "unsupported_category": "none",
            "route": "review_semantic_plus_sql",
            "answer_language": "en",
            "semantic_query": "shows leadership potential",
            "semantic_scope": "future_potential",
            "query": {
                "base_table": "employees",
                "select": [
                    {
                        "field": "employees.employee_id",
                        "aggregate": None,
                        "distinct": False,
                        "alias": None,
                    }
                ],
                "filters": [
                    {
                        "field": "departments.department_name",
                        "operator": "eq",
                        "value": "Engineering",
                    }
                ],
                "group_by": [],
                "order_by": [],
                "limit": None,
            },
        }
        matches = [review_match(1), review_match(4, "David", "Sales")]
        traced = self.service([plan], matches).answer_with_trace(
            "Which Engineering employees show leadership potential?"
        )
        self.assertEqual(
            [{"employee_id": "1"}],
            traced["evidence"]["result"]["rows"],
        )
        self.assertEqual(
            ["Engineering", 1, 4, 1, 4],
            traced["evidence"]["sql_parameters"],
        )

    def test_invalid_field_fails_closed(self):
        plan = sql_plan()
        plan["query"]["select"][0]["field"] = "employees.secret"
        traced = self.service([plan]).answer_with_trace("Show secrets")
        self.assertEqual("unsupported", traced["evidence"]["status"])
        self.assertEqual("", traced["evidence"]["sql"])

    def test_planner_failure_fails_closed(self):
        traced = self.service([None, None]).answer_with_trace("Show employees")
        self.assertEqual("unsupported", traced["evidence"]["status"])
        self.assertEqual("unavailable", traced["evidence"]["route_used"])

    def test_oversized_question_is_rejected_without_azure_call(self):
        client = FakeClient([])
        service = HRAgentService(
            self.settings,
            database=self.database,
            client=client,
            retriever=FakeRetriever([]),
        )
        traced = service.answer_with_trace("x" * 4001)
        self.assertEqual("unsupported", traced["evidence"]["status"])
        self.assertIn("4,000-character", traced["evidence"]["reason"])

    def test_all_unsupported_categories_are_evidenced_without_query_execution(self):
        for category in (
            "vague",
            "out_of_scope",
            "unavailable_data",
            "unsupported_operation",
        ):
            with self.subTest(category=category):
                plan = {
                    "supported": False,
                    "unsupported_category": category,
                    "route": "sql_only",
                    "answer_language": "en",
                    "semantic_query": "",
                    "semantic_scope": "none",
                    "query": None,
                }
                traced = self.service([plan]).answer_with_trace("Boundary request")
                evidence = traced["evidence"]
                self.assertEqual(category, evidence["unsupported_category"])
                self.assertEqual("audited_azure_plan", evidence["classification_source"])
                self.assertTrue(evidence["classification_basis"])
                self.assertTrue(evidence["available_data"])
                self.assertEqual("none", evidence["route_used"])
                self.assertEqual("", evidence["sql"])
                self.assertIsNone(evidence["result"])

    def test_unsupported_guidance_is_grounded_and_exposed_as_evidence(self):
        plan = {
            "supported": False,
            "unsupported_category": "unavailable_data",
            "route": "sql_only",
            "answer_language": "en",
            "semantic_query": "",
            "semantic_scope": "none",
            "query": None,
        }
        guidance = {
            "answer": (
                "I cannot answer the policy question because policy data is not "
                "available. I can help with recorded absence information."
            ),
        }
        traced = self.service([plan, guidance]).answer_with_trace(
            "What is the parental-leave policy?",
            use_ai_formulation=True,
        )
        evidence = traced["evidence"]
        self.assertEqual(guidance["answer"], traced["answer"])
        self.assertEqual("azure_grounded_guidance", evidence["guidance_source"])
        self.assertEqual("unavailable_data", evidence["unsupported_category"])

    def test_invalid_unsupported_guidance_keeps_safe_localized_fallback(self):
        plan = {
            "supported": False,
            "unsupported_category": "out_of_scope",
            "route": "sql_only",
            "answer_language": "en",
            "semantic_query": "",
            "semantic_scope": "none",
            "query": None,
        }
        invalid_guidance = {"answer": "unsafe", "extra": "unexpected"}
        traced = self.service([plan, invalid_guidance]).answer_with_trace(
            "What is tomorrow's weather?",
            use_ai_formulation=True,
        )
        self.assertEqual("Unsupported or vague question.", traced["answer"])
        self.assertEqual(
            "deterministic_fallback",
            traced["evidence"]["guidance_source"],
        )


if __name__ == "__main__":
    unittest.main()
