"""Run the frozen 100-question deterministic SQL benchmark once, without tuning."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from blind_holdout_cases import BLIND_HOLDOUT_CASES
from blind_holdout_cases_v2 import BLIND_HOLDOUT_CASES_V2
from prompt_freeze_sql_stress import (
    FROZEN_PLAN_AUDIT_PROMPT_SHA256,
    FROZEN_PLAN_AUDIT_PROMPT_VERSION,
    FROZEN_PLAN_REPAIR_POLICY_SHA256,
    FROZEN_PLAN_REPAIR_POLICY_VERSION,
    FROZEN_PLANNER_PROMPT_SHA256,
    FROZEN_PLANNER_PROMPT_VERSION,
    FROZEN_SQL_STRESS_CORPUS_SHA256,
)
from route_eval_cases import ROUTE_EVAL_CASES
from run_azure_blind_holdout import validate_case
from sql_stress_cases import LANGUAGES, SQL_STRESS_CASES
from ui_eval_cases import UI_EVAL_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.database import HRDatabase
from hr_agent.models import AgentPlan, QueryPlan, parse_agent_plan
from hr_agent.planner import (
    PLAN_AUDIT_PROMPT_SHA256,
    PLAN_AUDIT_PROMPT_VERSION,
    PLAN_AUDIT_SYSTEM_PROMPT,
    PLAN_REPAIR_POLICY_SHA256,
    PLAN_REPAIR_POLICY_VERSION,
    PLANNER_PROMPT_SHA256,
    PLANNER_PROMPT_VERSION,
    PLANNER_SYSTEM_PROMPT,
    plan_question,
)
from hr_agent.query_builder import QueryBuildError, build_query
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 260


def corpus_sha256() -> str:
    encoded = json.dumps(
        SQL_STRESS_CASES,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def expected_plan(item: dict) -> AgentPlan:
    select = []
    for index, (field, aggregate) in enumerate(item["select"], start=1):
        select.append(
            {
                "field": field,
                "aggregate": aggregate,
                "distinct": False,
                "alias": f"expected_value_{index}" if aggregate else None,
            }
        )
    filters = [
        {
            "field": field,
            "operator": operator,
            "value": list(value) if isinstance(value, tuple) else value,
        }
        for field, operator, value in item["filters"]
    ]
    order_by = [
        {"field": field, "aggregate": aggregate, "direction": direction}
        for field, aggregate, direction in item["order_by"]
    ]
    return parse_agent_plan(
        {
            "supported": True,
            "unsupported_category": "none",
            "route": "sql_only",
            "answer_language": item["language"],
            "semantic_query": "",
            "semantic_scope": "none",
            "query": {
                "base_table": item["base"],
                "select": select,
                "filters": filters,
                "group_by": list(item["group_by"]),
                "order_by": order_by,
                "limit": item["limit"],
            },
        }
    )


def prior_questions() -> set[str]:
    questions = {question.casefold() for question, _route in ROUTE_EVAL_CASES}
    questions.update(item["question"].casefold() for item in BLIND_HOLDOUT_CASES)
    questions.update(item["question"].casefold() for item in BLIND_HOLDOUT_CASES_V2)
    questions.update(item.question.casefold() for item in UI_EVAL_CASES)
    return questions


def preflight() -> list[str]:
    failures = []
    identities = (
        (PLANNER_PROMPT_VERSION, FROZEN_PLANNER_PROMPT_VERSION, "planner version"),
        (PLANNER_PROMPT_SHA256, FROZEN_PLANNER_PROMPT_SHA256, "planner hash"),
        (
            PLAN_AUDIT_PROMPT_VERSION,
            FROZEN_PLAN_AUDIT_PROMPT_VERSION,
            "auditor version",
        ),
        (
            PLAN_AUDIT_PROMPT_SHA256,
            FROZEN_PLAN_AUDIT_PROMPT_SHA256,
            "auditor hash",
        ),
        (
            PLAN_REPAIR_POLICY_VERSION,
            FROZEN_PLAN_REPAIR_POLICY_VERSION,
            "repair version",
        ),
        (
            PLAN_REPAIR_POLICY_SHA256,
            FROZEN_PLAN_REPAIR_POLICY_SHA256,
            "repair hash",
        ),
        (corpus_sha256(), FROZEN_SQL_STRESS_CORPUS_SHA256, "corpus hash"),
    )
    for actual, expected, label in identities:
        if actual != expected:
            failures.append(f"{label} changed: expected={expected} actual={actual}")

    if len(SQL_STRESS_CASES) != 100:
        failures.append(f"expected 100 cases, found {len(SQL_STRESS_CASES)}")
    language_counts = Counter(item["language"] for item in SQL_STRESS_CASES)
    if language_counts != Counter({language: 20 for language in LANGUAGES}):
        failures.append(f"unbalanced languages: {dict(language_counts)}")

    previous = prior_questions()
    production_prompts = (
        PLANNER_SYSTEM_PROMPT + "\n" + PLAN_AUDIT_SYSTEM_PROMPT
    ).casefold()
    current = set()
    for index, item in enumerate(SQL_STRESS_CASES, start=1):
        folded = re.sub(r"\s+", " ", item["question"].strip()).casefold()
        if folded in current:
            failures.append(f"case {index} duplicates another stress case")
        if folded in previous:
            failures.append(f"case {index} duplicates a prior evaluated question")
        if folded in production_prompts:
            failures.append(f"case {index} appears in a production prompt")
        current.add(folded)
        try:
            plan = expected_plan(item)
            if plan.query is None:
                failures.append(f"case {index} expected plan has no query")
            else:
                build_query(plan.query)
        except Exception as error:
            failures.append(f"case {index} invalid expectation: {error}")
    return failures


def selection_keys(query: QueryPlan) -> tuple[tuple[str, str | None], ...]:
    return tuple((item.field, item.aggregate) for item in query.select)


def execute_canonical(
    database: HRDatabase,
    query: QueryPlan,
    expected_keys: tuple[tuple[str, str | None], ...],
) -> tuple[tuple[object, ...], ...] | None:
    actual_keys = selection_keys(query)
    if len(actual_keys) != len(expected_keys) or set(actual_keys) != set(expected_keys):
        return None
    built = build_query(query)
    _columns, rows = database.execute(built.sql, built.parameters)
    positions = [actual_keys.index(key) for key in expected_keys]
    return tuple(tuple(row[position] for position in positions) for row in rows)


def main() -> int:
    preflight_failures = preflight()
    if preflight_failures:
        for failure in preflight_failures:
            print("PREFLIGHT FAILURE " + failure)
        return 2
    print(
        "Frozen SQL stress preflight passed: "
        f"cases={len(SQL_STRESS_CASES)} corpus_sha256={corpus_sha256()}",
        flush=True,
    )
    if len(sys.argv) == 2 and sys.argv[1] == "--preflight":
        return 0

    required = {
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
    }
    missing = configure_private_environment(required)
    if missing:
        print("Missing required configuration: " + ", ".join(missing))
        return 2

    transport = AzureUsageTransport(MAX_AZURE_CALLS)
    client = AzureOpenAIClient(Settings.from_environment(), transport=transport)
    database = HRDatabase.from_project_files()

    exact_passes = 0
    result_passes = 0
    executable_passes = 0
    route_passes = 0
    language_passes = 0
    exact_by_language = Counter()
    result_by_language = Counter()
    exact_by_category = Counter()
    result_by_category = Counter()
    failures = []

    for index, item in enumerate(SQL_STRESS_CASES, start=1):
        plan = plan_question(client, item["question"])
        exact_errors = validate_case(item, plan)
        route_ok = bool(plan and plan.supported and plan.route == "sql_only")
        language_ok = bool(plan and plan.answer_language == item["language"])
        executable = False
        result_ok = False
        result_error = ""

        expected = expected_plan(item)
        assert expected.query is not None
        expected_keys = selection_keys(expected.query)
        expected_rows = execute_canonical(database, expected.query, expected_keys)
        try:
            if plan is not None and plan.supported and plan.query is not None:
                build_query(plan.query)
                executable = True
                actual_rows = execute_canonical(database, plan.query, expected_keys)
                result_ok = actual_rows == expected_rows
                if actual_rows is None:
                    result_error = "requested result columns differ"
                elif not result_ok:
                    result_error = (
                        f"expected_rows={expected_rows!r} actual_rows={actual_rows!r}"
                    )
            else:
                result_error = "no supported structured plan"
        except QueryBuildError as error:
            result_error = f"query does not compile: {error}"

        if not exact_errors:
            exact_passes += 1
            exact_by_language[item["language"]] += 1
            exact_by_category[item["category"]] += 1
        if result_ok:
            result_passes += 1
            result_by_language[item["language"]] += 1
            result_by_category[item["category"]] += 1
        if executable:
            executable_passes += 1
        if route_ok:
            route_passes += 1
        if language_ok:
            language_passes += 1
        if exact_errors or not result_ok:
            failures.append(
                {
                    "index": index,
                    "intent": item["intent"],
                    "category": item["category"],
                    "language": item["language"],
                    "question": item["question"],
                    "exact_errors": exact_errors,
                    "result_error": result_error,
                    "plan": repr(plan),
                }
            )

        if index % 10 == 0:
            print(
                f"Evaluated {index}/100: exact={exact_passes} "
                f"results={result_passes} executable={executable_passes}",
                flush=True,
            )
        time.sleep(0.25)

    print(
        "Frozen SQL stress result: "
        f"exact_intent={exact_passes}/100; executed_result={result_passes}/100; "
        f"executable={executable_passes}/100; route={route_passes}/100; "
        f"language={language_passes}/100; "
        f"exact_by_language={dict(exact_by_language)}; "
        f"result_by_language={dict(result_by_language)}; "
        f"exact_by_category={dict(exact_by_category)}; "
        f"result_by_category={dict(result_by_category)}; "
        + transport.usage_summary(),
        flush=True,
    )
    for failure in failures:
        print("SQL STRESS MISMATCH " + json.dumps(failure, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
