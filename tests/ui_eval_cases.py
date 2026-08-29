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
    scalar_value: int | None = None
    semantic_ids: frozenset[int] | None = None
    final_ids: frozenset[int] | None = None


UI_EVAL_CASES = (
    UIEvalCase(
        "Show active Engineering employees earning at least 70000.",
        "sql_only", "en", row_count=6,
    ),
    UIEvalCase(
        "How many employees work in each department?",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "List the three most recently hired employees.",
        "sql_only", "en", row_count=3,
    ),
    UIEvalCase(
        "Show unpaid vacation absences lasting at least 5 days.",
        "sql_only", "en", status="empty", row_count=0,
    ),
    UIEvalCase(
        "Who currently demonstrates strong organizational skills?",
        "review_semantic", "en", semantic_scope="current_strength",
        semantic_ids=frozenset({3, 11}),
    ),
    UIEvalCase(
        "Who shows future potential to lead others?",
        "review_semantic", "en", semantic_scope="future_potential",
        semantic_ids=frozenset({1}),
    ),
    UIEvalCase(
        "Who needs to become more confident?",
        "review_semantic", "en", semantic_scope="development_need",
        semantic_ids=frozenset({12}),
    ),
    UIEvalCase(
        "Who is ready now to take responsibility for a team?",
        "review_semantic", "en", semantic_scope="readiness",
        semantic_ids=frozenset({4, 6, 11}),
    ),
    UIEvalCase(
        "How many Engineering employees currently demonstrate analytical strength?",
        "review_semantic_plus_sql", "en", semantic_scope="current_strength",
        scalar_value=1, semantic_ids=frozenset({13}),
    ),
    UIEvalCase(
        "Show Sales employees currently praised for teamwork.",
        "review_semantic_plus_sql", "en", semantic_scope="current_strength",
        semantic_ids=frozenset({4, 9}), final_ids=frozenset({4}),
    ),
    UIEvalCase(
        "List the two highest-paid employees who currently solve problems well.",
        "review_semantic_plus_sql", "en", semantic_scope="current_strength",
        semantic_ids=frozenset({1, 14}), final_ids=frozenset({1, 14}),
    ),
    UIEvalCase(
        "Which active HR employees need stronger communication skills?",
        "review_semantic_plus_sql", "en", status="empty",
        semantic_scope="development_need", row_count=0,
        semantic_ids=frozenset({1}), final_ids=frozenset(),
    ),
    UIEvalCase(
        "Wie viele aktive Mitarbeiter arbeiten im Vertrieb?",
        "sql_only", "de", scalar_value=3,
    ),
    UIEvalCase(
        "Quels employés des ventes ont actuellement de solides compétences en négociation ?",
        "review_semantic_plus_sql", "fr", semantic_scope="current_strength",
        semantic_ids=frozenset({4}), final_ids=frozenset({4}),
    ),
    UIEvalCase(
        "¿Quién muestra potencial futuro para liderar a otras personas?",
        "review_semantic", "es", semantic_scope="future_potential",
        semantic_ids=frozenset({1}),
    ),
    UIEvalCase(
        "كم عدد الموظفين في قسم الموارد البشرية؟",
        "sql_only", "ar", scalar_value=4,
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

assert len(UI_EVAL_CASES) == 22
