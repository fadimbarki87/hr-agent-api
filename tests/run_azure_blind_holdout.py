"""Run the frozen, one-time multilingual planner acceptance holdout."""

from __future__ import annotations

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
from prompt_freeze import (
    FROZEN_PLANNER_PROMPT_SHA256,
    FROZEN_PLANNER_PROMPT_VERSION,
    FROZEN_RERANK_PROMPT_SHA256,
    FROZEN_RERANK_PROMPT_VERSION,
)
from route_eval_cases import ROUTE_EVAL_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.planner import (
    PLANNER_PROMPT_SHA256,
    PLANNER_PROMPT_VERSION,
    PLANNER_SYSTEM_PROMPT,
    plan_question,
)
from hr_agent.query_builder import QueryBuildError, build_query
from hr_agent.retrieval import (
    RERANK_PROMPT_SHA256,
    RERANK_PROMPT_VERSION,
    RERANK_SYSTEM_PROMPT,
)
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 90


def normalized_value(value):
    if isinstance(value, list):
        return tuple(value)
    return value


def validate_case(expected, plan) -> list[str]:
    errors = []
    if plan is None:
        return ["no valid plan"]
    if plan.supported != expected["supported"]:
        errors.append(f"supported expected={expected['supported']} actual={plan.supported}")
    if plan.route != expected["route"]:
        errors.append(f"route expected={expected['route']} actual={plan.route}")
    if plan.answer_language != expected["language"]:
        errors.append(
            f"language expected={expected['language']} actual={plan.answer_language}"
        )
    if plan.semantic_scope != expected["scope"]:
        errors.append(
            f"scope expected={expected['scope']} actual={plan.semantic_scope}"
        )
    if not expected["supported"]:
        return errors
    if expected["route"] == "review_semantic":
        if not plan.semantic_query or plan.query is not None:
            errors.append("semantic-only shape is incomplete")
        return errors
    if plan.query is None:
        errors.append("missing structured query")
        return errors

    query = plan.query
    if query.base_table != expected["base"]:
        errors.append(f"base expected={expected['base']} actual={query.base_table}")
    actual_select = tuple((item.field, item.aggregate) for item in query.select)
    if actual_select != expected["select"]:
        errors.append(f"select expected={expected['select']} actual={actual_select}")
    actual_filters = {
        (item.field, item.operator, normalized_value(item.value))
        for item in query.filters
    }
    expected_filters = set(expected["filters"])
    if actual_filters != expected_filters:
        errors.append(
            f"filters expected={sorted(map(str, expected_filters))} "
            f"actual={sorted(map(str, actual_filters))}"
        )
    if query.group_by != expected["group_by"]:
        errors.append(f"group_by expected={expected['group_by']} actual={query.group_by}")
    actual_order = tuple(
        (item.field, item.aggregate, item.direction) for item in query.order_by
    )
    if actual_order != expected["order_by"]:
        errors.append(f"order expected={expected['order_by']} actual={actual_order}")
    if query.limit != expected["limit"]:
        errors.append(f"limit expected={expected['limit']} actual={query.limit}")
    try:
        build_query(
            query,
            semantic_candidate_ids=[1, 2]
            if plan.route == "review_semantic_plus_sql"
            else None,
        )
    except QueryBuildError as error:
        errors.append(f"query does not compile: {error}")
    return errors


def assert_frozen_and_unseen() -> list[str]:
    failures = []
    identities = (
        (PLANNER_PROMPT_VERSION, FROZEN_PLANNER_PROMPT_VERSION, "planner version"),
        (PLANNER_PROMPT_SHA256, FROZEN_PLANNER_PROMPT_SHA256, "planner hash"),
        (RERANK_PROMPT_VERSION, FROZEN_RERANK_PROMPT_VERSION, "reranker version"),
        (RERANK_PROMPT_SHA256, FROZEN_RERANK_PROMPT_SHA256, "reranker hash"),
    )
    for actual, expected, label in identities:
        if actual != expected:
            failures.append(f"{label} changed: expected={expected} actual={actual}")

    prior_questions = {question.casefold() for question, _route in ROUTE_EVAL_CASES}
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    prior_questions.update(
        question.casefold() for question in re.findall(r"<li>(.*?)</li>", html)
    )
    seen = set()
    prompt_text = (PLANNER_SYSTEM_PROMPT + "\n" + RERANK_SYSTEM_PROMPT).casefold()
    for index, item in enumerate(BLIND_HOLDOUT_CASES, start=1):
        question = item["question"].strip()
        folded = question.casefold()
        if folded in seen:
            failures.append(f"case {index} duplicates another holdout question")
        if folded in prior_questions:
            failures.append(f"case {index} duplicates a prior evaluation question")
        if folded in prompt_text:
            failures.append(f"case {index} appears in a production prompt")
        seen.add(folded)
    return failures


def main() -> int:
    preflight_failures = assert_frozen_and_unseen()
    if preflight_failures:
        for failure in preflight_failures:
            print("PREFLIGHT FAILURE " + failure)
        return 2

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
    failures = []
    route_passes = {"sql_only": 0, "review_semantic": 0,
                    "review_semantic_plus_sql": 0}
    route_totals = dict.fromkeys(route_passes, 0)
    language_passes = {language: 0 for language in ("en", "de", "fr", "es", "ar")}
    language_totals = dict.fromkeys(language_passes, 0)

    for index, expected in enumerate(BLIND_HOLDOUT_CASES, start=1):
        plan = plan_question(client, expected["question"])
        errors = validate_case(expected, plan)
        route_totals[expected["route"]] += 1
        language_totals[expected["language"]] += 1
        if errors:
            failures.append((index, expected["question"], errors, plan))
        else:
            route_passes[expected["route"]] += 1
            language_passes[expected["language"]] += 1
        if index % 10 == 0:
            print(f"Evaluated {index}/{len(BLIND_HOLDOUT_CASES)}", flush=True)
        time.sleep(0.5)

    passed = len(BLIND_HOLDOUT_CASES) - len(failures)
    print(
        f"Frozen blind planner holdout: {passed}/{len(BLIND_HOLDOUT_CASES)} "
        f"fully correct; by_route={route_passes}/{route_totals}; "
        f"by_language={language_passes}/{language_totals}; "
        + transport.usage_summary()
    )
    for index, question, errors, plan in failures:
        print(
            f"HOLDOUT MISMATCH {index:02}: {question}; "
            f"errors={json.dumps(errors, ensure_ascii=False)}; plan={plan!r}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
