"""Typed acceptance contract for every selectable website example."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UIEvalCase:
    question: str
    route: str
    language: str
    status: str = "supported"
    unsupported_category: str = "none"
    semantic_scope: str = "none"
    row_count: int | None = None
    scalar_value: int | float | str | None = None
    semantic_ids: frozenset[int] | None = None
    final_ids: frozenset[int] | None = None


UI_EVAL_CASES = (
    UIEvalCase(
        "Show all employees in Engineering.",
        "sql_only", "en", row_count=8,
    ),
    UIEvalCase(
        "Show the email and salary of employees in Sales.",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "Show employees with salary between 60000 and 90000.",
        "sql_only", "en",
    ),
    UIEvalCase(
        "List employees hired before 2020.",
        "sql_only", "en",
    ),
    UIEvalCase(
        "How many employees are in each department?",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "What is the average salary in Engineering?",
        "sql_only", "en", row_count=1, scalar_value=75625.0,
    ),
    UIEvalCase(
        "Top 3 highest paid employees.",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "Which departments have budget greater than 200000?",
        "sql_only", "en", row_count=2,
    ),
    UIEvalCase(
        "List active Sales employees' first names, last names, and emails, sorted alphabetically by last name.",
        "sql_only", "en", row_count=3, final_ids=frozenset({4, 8, 12}),
    ),
    UIEvalCase(
        "For each department, show the department name and total employee salary.",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "Show the four newest hires with their first names, last names, and hire dates.",
        "sql_only", "en", row_count=4,
        final_ids=frozenset({5, 10, 12, 13}),
    ),
    UIEvalCase(
        "List first names, last names, and hire dates for employees hired between 2020-01-01 and 2021-12-31 inclusive.",
        "sql_only", "en", row_count=6,
        final_ids=frozenset({1, 3, 7, 9, 13, 15}),
    ),
    UIEvalCase(
        "Who reports to Bob Schmidt?",
        "sql_only", "en",
    ),
    UIEvalCase(
        "Who is the manager of Greta Wolf?",
        "sql_only", "en", row_count=1,
    ),
    UIEvalCase(
        "Show all sick absences.",
        "sql_only", "en",
    ),
    UIEvalCase(
        "Show absences for Alice Müller.",
        "sql_only", "en",
    ),
    UIEvalCase(
        "Wie viele aktive Mitarbeiter arbeiten im Vertrieb?",
        "sql_only", "de", scalar_value=3,
    ),
    UIEvalCase(
        "Quels sont les employés actifs du service des ventes ?",
        "sql_only", "fr", row_count=3,
    ),
    UIEvalCase(
        "¿Qué empleados trabajan en el departamento de Ingeniería?",
        "sql_only", "es", row_count=8,
    ),
    UIEvalCase(
        "كم عدد الموظفين في قسم الموارد البشرية؟",
        "sql_only", "ar", scalar_value=4,
    ),
    UIEvalCase(
        "Who currently demonstrates strong organizational skills?",
        "review_semantic", "en", semantic_scope="current_strength",
        semantic_ids=frozenset({3, 11}),
    ),
    UIEvalCase(
        "Show Sales employees currently praised for teamwork.",
        "review_semantic_plus_sql", "en", semantic_scope="current_strength",
        semantic_ids=frozenset({4, 9}), final_ids=frozenset({4}),
    ),
    UIEvalCase(
        "Show employees whose performance review literally contains the phrase high-quality work.",
        "sql_only", "en", row_count=1,
    ),
    UIEvalCase(
        "What is the company's remote-work policy?",
        "none", "en", status="unsupported",
        unsupported_category="unavailable_data",
    ),
    UIEvalCase(
        "Show employees in the Finance department.",
        "none", "en", status="unsupported",
        unsupported_category="unavailable_data",
    ),
    UIEvalCase(
        "Show active employees hired after 2035-01-01.",
        "sql_only", "en", status="empty", row_count=0,
    ),
    UIEvalCase(
        "What about them?",
        "none", "en", status="unsupported",
        unsupported_category="vague",
    ),
    UIEvalCase(
        "What will the weather be in Paris tomorrow?",
        "none", "en", status="unsupported",
        unsupported_category="out_of_scope",
    ),
)

assert len(UI_EVAL_CASES) == 28
