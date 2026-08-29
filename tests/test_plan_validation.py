import unittest

from hr_agent.models import PlanValidationError, parse_agent_plan


def valid_query():
    return {
        "base_table": "employees",
        "select": [
            {
                "field": "employees.first_name",
                "aggregate": None,
                "distinct": False,
                "alias": None,
            }
        ],
        "filters": [],
        "group_by": [],
        "order_by": [],
        "limit": None,
    }


def valid_plan():
    return {
        "supported": True,
        "unsupported_category": "none",
        "route": "sql_only",
        "answer_language": "en",
        "semantic_query": "",
        "semantic_scope": "none",
        "query": valid_query(),
    }


class PlanValidationTests(unittest.TestCase):
    def test_accepts_strict_sql_plan(self):
        plan = parse_agent_plan(valid_plan())
        self.assertTrue(plan.supported)
        self.assertEqual("employees", plan.query.base_table)

    def test_accepts_semantic_plan_without_query(self):
        payload = valid_plan()
        payload.update(
            route="review_semantic",
            answer_language="de",
            semantic_query="shows leadership potential",
            semantic_scope="future_potential",
            query=None,
        )
        plan = parse_agent_plan(payload)
        self.assertEqual("de", plan.answer_language)
        self.assertIsNone(plan.query)

    def test_rejects_unknown_top_level_key(self):
        payload = valid_plan()
        payload["sql"] = "DROP TABLE employees"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_unknown_nested_key(self):
        payload = valid_plan()
        payload["query"]["filters"] = [
            {
                "field": "employees.salary",
                "operator": "gt",
                "value": 1,
                "raw_sql": "OR 1=1",
            }
        ]
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_semantic_route_without_semantic_query(self):
        payload = valid_plan()
        payload.update(route="review_semantic", query=None)
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_hybrid_route_without_query(self):
        payload = valid_plan()
        payload.update(
            route="review_semantic_plus_sql",
            semantic_query="mentors colleagues",
            semantic_scope="current_strength",
            query=None,
        )
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_invalid_language(self):
        payload = valid_plan()
        payload["answer_language"] = "English"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_unbounded_limit(self):
        payload = valid_plan()
        payload["query"]["limit"] = 1001
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_nonempty_unsupported_plan(self):
        payload = valid_plan()
        payload["supported"] = False
        payload["unsupported_category"] = "unavailable_data"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_accepts_each_closed_unsupported_category(self):
        for category in (
            "vague",
            "out_of_scope",
            "unavailable_data",
            "unsupported_operation",
        ):
            with self.subTest(category=category):
                payload = valid_plan()
                payload.update(
                    supported=False,
                    unsupported_category=category,
                    query=None,
                )
                plan = parse_agent_plan(payload)
                self.assertFalse(plan.supported)
                self.assertEqual(category, plan.unsupported_category)

    def test_rejects_inconsistent_or_unknown_unsupported_category(self):
        payload = valid_plan()
        payload["unsupported_category"] = "vague"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

        payload = valid_plan()
        payload.update(
            supported=False,
            unsupported_category="other",
            query=None,
        )
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_semantic_text_on_sql_only_route(self):
        payload = valid_plan()
        payload["semantic_query"] = "hidden qualitative criterion"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_oversized_semantic_query(self):
        payload = valid_plan()
        payload.update(
            route="review_semantic",
            semantic_query="x" * 501,
            semantic_scope="neutral",
            query=None,
        )
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_missing_or_invalid_semantic_scope(self):
        payload = valid_plan()
        del payload["semantic_scope"]
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

        payload = valid_plan()
        payload["semantic_scope"] = "leadership"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_aggregate_without_alias_before_query_building(self):
        payload = valid_plan()
        payload["query"]["select"] = [
            {
                "field": "employees.salary",
                "aggregate": "avg",
                "distinct": False,
                "alias": None,
            }
        ]
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_unknown_field_before_query_building(self):
        payload = valid_plan()
        payload["query"]["select"][0]["field"] = "employees.private_note"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_nested_filter_value_before_query_building(self):
        payload = valid_plan()
        payload["query"]["filters"] = [
            {
                "field": "departments.department_name",
                "operator": "in",
                "value": [{"subquery": "not allowed"}],
            }
        ]
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_accepts_only_documented_department_values(self):
        payload = valid_plan()
        payload["query"]["filters"] = [
            {
                "field": "departments.department_name",
                "operator": "eq",
                "value": "Engineering",
            }
        ]
        self.assertEqual(
            "Engineering",
            parse_agent_plan(payload).query.filters[0].value,
        )

        payload["query"]["filters"][0]["value"] = "Marketing"
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)

    def test_rejects_unknown_absence_value_inside_in_filter(self):
        payload = valid_plan()
        payload["query"]["filters"] = [
            {
                "field": "absences.absence_type",
                "operator": "in",
                "value": ["paid_vacation", "parental_leave"],
            }
        ]
        with self.assertRaises(PlanValidationError):
            parse_agent_plan(payload)


if __name__ == "__main__":
    unittest.main()
