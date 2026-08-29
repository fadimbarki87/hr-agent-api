import unittest

from hr_agent.database import HRDatabase
from hr_agent.models import (
    FilterExpression,
    OrderExpression,
    QueryPlan,
    SelectExpression,
)
from hr_agent.query_builder import QueryBuildError, build_query


def query_plan(
    base_table,
    select,
    *,
    filters=(),
    group_by=(),
    order_by=(),
    limit=None,
):
    return QueryPlan(
        base_table=base_table,
        select=tuple(select),
        filters=tuple(filters),
        group_by=tuple(group_by),
        order_by=tuple(order_by),
        limit=limit,
    )


class QueryBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = HRDatabase.from_project_files()

    def execute(self, plan, candidate_ids=None):
        built = build_query(plan, semantic_candidate_ids=candidate_ids)
        columns, rows = self.database.execute(built.sql, built.parameters)
        return built, columns, rows

    def test_department_filter_returns_all_engineering_employees(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[FilterExpression("departments.department_name", "eq", "engineering")],
        )
        built, _, rows = self.execute(plan)
        self.assertEqual([1, 2, 5, 6, 9, 10, 13, 14], [row[0] for row in rows])
        self.assertNotIn("engineering", built.sql.lower())
        self.assertEqual(("engineering",), built.parameters)

    def test_reports_to_uses_validated_self_join(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[
                FilterExpression("manager.first_name", "eq", "Frank"),
                FilterExpression("manager.last_name", "eq", "Neumann"),
            ],
        )
        built, _, rows = self.execute(plan)
        self.assertIn("JOIN employees m", built.sql)
        self.assertEqual([9, 13, 14], [row[0] for row in rows])

    def test_manager_of_employee_selects_manager_fields(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression("manager.first_name"),
                SelectExpression("manager.last_name"),
            ],
            filters=[
                FilterExpression("employees.first_name", "eq", "Greta"),
                FilterExpression("employees.last_name", "eq", "Wolf"),
            ],
        )
        _, _, rows = self.execute(plan)
        self.assertEqual([("Clara", "Fischer")], rows)

    def test_absence_query_joins_employee_and_department(self):
        plan = query_plan(
            "absences",
            [SelectExpression("absences.absence_id")],
            filters=[
                FilterExpression("absences.absence_type", "eq", "sick"),
                FilterExpression("departments.department_name", "eq", "Engineering"),
            ],
        )
        built, _, rows = self.execute(plan)
        self.assertIn("JOIN employees e", built.sql)
        self.assertIn("JOIN departments d", built.sql)
        self.assertEqual([1, 2], [row[0] for row in rows])

    def test_grouped_employee_count_is_correct_and_ordered(self):
        plan = query_plan(
            "departments",
            [
                SelectExpression("departments.department_name"),
                SelectExpression(
                    "employees.employee_id",
                    aggregate="count",
                    alias="employee_count",
                ),
            ],
            group_by=["departments.department_name"],
        )
        _, columns, rows = self.execute(plan)
        self.assertEqual(["department_name", "employee_count"], columns)
        self.assertEqual([("Engineering", 8), ("HR", 4), ("Sales", 3)], rows)

    def test_top_salary_has_stable_tie_breaker_and_parameterized_limit(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression("employees.employee_id"),
                SelectExpression("employees.salary"),
            ],
            order_by=[OrderExpression("employees.salary", "desc")],
            limit=3,
        )
        built, _, rows = self.execute(plan)
        self.assertTrue(built.sql.endswith("LIMIT ?"))
        self.assertEqual((3,), built.parameters)
        self.assertEqual([(6, 105000), (9, 95000), (2, 90000)], rows)

    def test_literal_review_search_is_parameterized(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[
                FilterExpression(
                    "employees.performance_review",
                    "contains",
                    "leadership",
                )
            ],
        )
        built, _, rows = self.execute(plan)
        self.assertNotIn("leadership", built.sql)
        self.assertEqual(("%leadership%",), built.parameters)
        self.assertEqual([1, 4, 6], [row[0] for row in rows])

    def test_like_wildcards_in_user_value_are_escaped(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[FilterExpression("employees.first_name", "contains", "%_")],
        )
        built = build_query(plan)
        self.assertEqual(("%\\%\\_%",), built.parameters)

    def test_hybrid_candidates_are_injected_as_parameters(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[FilterExpression("departments.department_name", "eq", "Engineering")],
        )
        built, _, rows = self.execute(plan, [1, 4, 6, 1])
        self.assertEqual(
            ("Engineering", 1, 4, 6, 1, 4, 6),
            built.parameters,
        )
        self.assertEqual([1, 6], [row[0] for row in rows])

    def test_semantic_relevance_order_is_preserved_without_structured_sort(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            limit=2,
        )
        built, _, rows = self.execute(plan, [14, 1])
        self.assertIn("CASE e.employee_id", built.sql)
        self.assertEqual([14, 1], [row[0] for row in rows])

    def test_empty_hybrid_candidates_produce_a_real_zero_count(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression(
                    "employees.employee_id",
                    aggregate="count",
                    alias="employee_count",
                )
            ],
        )
        built, _, rows = self.execute(plan, [])
        self.assertIn("1 = 0", built.sql)
        self.assertEqual([(0,)], rows)

    def test_between_filter_preserves_numeric_values(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.employee_id")],
            filters=[FilterExpression("employees.salary", "between", [60000, 90000])],
        )
        _, _, rows = self.execute(plan)
        self.assertEqual([1, 2, 3, 4, 8, 11, 13, 14], [row[0] for row in rows])

    def test_rejects_unknown_field(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.password")],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan)

    def test_rejects_sql_injection_alias(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression(
                    "employees.salary",
                    aggregate="max",
                    alias='x"; DROP TABLE employees;--',
                )
            ],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan)

    def test_rejects_aggregate_without_alias(self):
        plan = query_plan(
            "employees",
            [SelectExpression("employees.salary", aggregate="avg")],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan)

    def test_rejects_ungrouped_selected_field_in_aggregate_query(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression("departments.department_name"),
                SelectExpression(
                    "employees.salary",
                    aggregate="max",
                    alias="maximum_salary",
                ),
            ],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan)

    def test_rejects_duplicate_result_column_names(self):
        plan = query_plan(
            "employees",
            [
                SelectExpression("employees.first_name"),
                SelectExpression("manager.first_name"),
            ],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan)

    def test_rejects_hybrid_candidates_for_wrong_base_table(self):
        plan = query_plan(
            "departments",
            [SelectExpression("departments.department_name")],
        )
        with self.assertRaises(QueryBuildError):
            build_query(plan, semantic_candidate_ids=[1])


if __name__ == "__main__":
    unittest.main()
