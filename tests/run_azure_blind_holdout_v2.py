"""Run the frozen v2 acceptance set through planner and independent auditor."""

from __future__ import annotations

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
from prompt_freeze_v2 import (
    FROZEN_PLAN_AUDIT_PROMPT_SHA256,
    FROZEN_PLAN_AUDIT_PROMPT_VERSION,
    FROZEN_PLAN_REPAIR_POLICY_SHA256,
    FROZEN_PLAN_REPAIR_POLICY_VERSION,
    FROZEN_PLANNER_PROMPT_SHA256,
    FROZEN_PLANNER_PROMPT_VERSION,
    FROZEN_RERANK_PROMPT_SHA256,
    FROZEN_RERANK_PROMPT_VERSION,
)
from route_eval_cases import ROUTE_EVAL_CASES
from run_azure_blind_holdout import validate_case

from hr_agent.azure_client import AzureOpenAIClient
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
from hr_agent.retrieval import (
    RERANK_PROMPT_SHA256,
    RERANK_PROMPT_VERSION,
    RERANK_SYSTEM_PROMPT,
)
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 90


def preflight() -> list[str]:
    failures = []
    identities = (
        (PLANNER_PROMPT_VERSION, FROZEN_PLANNER_PROMPT_VERSION, "planner version"),
        (PLANNER_PROMPT_SHA256, FROZEN_PLANNER_PROMPT_SHA256, "planner hash"),
        (PLAN_AUDIT_PROMPT_VERSION, FROZEN_PLAN_AUDIT_PROMPT_VERSION, "audit version"),
        (PLAN_AUDIT_PROMPT_SHA256, FROZEN_PLAN_AUDIT_PROMPT_SHA256, "audit hash"),
        (
            PLAN_REPAIR_POLICY_VERSION,
            FROZEN_PLAN_REPAIR_POLICY_VERSION,
            "repair policy version",
        ),
        (
            PLAN_REPAIR_POLICY_SHA256,
            FROZEN_PLAN_REPAIR_POLICY_SHA256,
            "repair policy hash",
        ),
        (RERANK_PROMPT_VERSION, FROZEN_RERANK_PROMPT_VERSION, "reranker version"),
        (RERANK_PROMPT_SHA256, FROZEN_RERANK_PROMPT_SHA256, "reranker hash"),
    )
    for actual, expected, label in identities:
        if actual != expected:
            failures.append(f"{label} changed: expected={expected} actual={actual}")

    prior = {question.casefold() for question, _route in ROUTE_EVAL_CASES}
    prior.update(item["question"].casefold() for item in BLIND_HOLDOUT_CASES)
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    prior.update(question.casefold() for question in re.findall(r"<li>(.*?)</li>", html))
    prompt = (
        PLANNER_SYSTEM_PROMPT + PLAN_AUDIT_SYSTEM_PROMPT + RERANK_SYSTEM_PROMPT
    ).casefold()
    current = set()
    for index, item in enumerate(BLIND_HOLDOUT_CASES_V2, start=1):
        question = item["question"].strip().casefold()
        if question in current:
            failures.append(f"case {index} duplicates v2")
        if question in prior:
            failures.append(f"case {index} duplicates prior evaluation")
        if question in prompt:
            failures.append(f"case {index} appears in a prompt")
        current.add(question)
    return failures


def main() -> int:
    failures = preflight()
    if failures:
        for failure in failures:
            print("PREFLIGHT FAILURE " + failure)
        return 2
    required = {
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_API_KEY",
    }
    missing = configure_private_environment(required)
    if missing:
        print("Missing required configuration: " + ", ".join(missing))
        return 2

    transport = AzureUsageTransport(MAX_AZURE_CALLS)
    client = AzureOpenAIClient(Settings.from_environment(), transport=transport)
    mismatches = []
    route_passes = {route: 0 for route in (
        "sql_only", "review_semantic", "review_semantic_plus_sql"
    )}
    route_totals = dict.fromkeys(route_passes, 0)
    language_passes = {language: 0 for language in ("en", "de", "fr", "es", "ar")}
    language_totals = dict.fromkeys(language_passes, 0)
    for index, expected in enumerate(BLIND_HOLDOUT_CASES_V2, start=1):
        plan = plan_question(client, expected["question"])
        errors = validate_case(expected, plan)
        route_totals[expected["route"]] += 1
        language_totals[expected["language"]] += 1
        if errors:
            mismatches.append((index, expected["question"], errors, plan))
        else:
            route_passes[expected["route"]] += 1
            language_passes[expected["language"]] += 1
        if index % 5 == 0:
            print(f"Evaluated {index}/{len(BLIND_HOLDOUT_CASES_V2)}", flush=True)
        time.sleep(0.5)

    passed = len(BLIND_HOLDOUT_CASES_V2) - len(mismatches)
    print(
        f"Frozen v2 audited holdout: {passed}/{len(BLIND_HOLDOUT_CASES_V2)} "
        f"fully correct; by_route={route_passes}/{route_totals}; "
        f"by_language={language_passes}/{language_totals}; "
        + transport.usage_summary()
    )
    for index, question, errors, plan in mismatches:
        print(
            f"V2 HOLDOUT MISMATCH {index:02}: {question}; "
            f"errors={errors!r}; plan={plan!r}"
        )
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
