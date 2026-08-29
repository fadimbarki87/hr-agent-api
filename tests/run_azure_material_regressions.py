"""Focused live checks derived from material v1 holdout failures."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from blind_holdout_cases import BLIND_HOLDOUT_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.planner import plan_question
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 20


def has_count(plan) -> bool:
    return bool(
        plan
        and plan.query
        and any(item.aggregate == "count" for item in plan.query.select)
    )


def main() -> int:
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

    client_transport = AzureUsageTransport(MAX_AZURE_CALLS)
    client = AzureOpenAIClient(
        Settings.from_environment(),
        transport=client_transport,
    )
    checks = [
        (4, lambda plan: plan is not None and plan.route == "sql_only" and has_count(plan)),
        (40, lambda plan: plan is not None and not plan.supported),
        (
            43,
            lambda plan: plan is not None
            and plan.route == "review_semantic_plus_sql"
            and has_count(plan),
        ),
        (
            58,
            lambda plan: plan is not None
            and plan.route == "review_semantic_plus_sql"
            and plan.query is not None
            and all(
                item.field != "employees.employment_status"
                for item in plan.query.filters
            ),
        ),
        (60, lambda plan: plan is not None and not plan.supported),
    ]
    failures = []
    for index, predicate in checks:
        question = BLIND_HOLDOUT_CASES[index - 1]["question"]
        plan = plan_question(client, question)
        passed = predicate(plan)
        print(f"{index:02} passed={passed} plan={plan!r}", flush=True)
        if not passed:
            failures.append(index)
    print(
        f"Material regression evaluation: {len(checks) - len(failures)}/"
        f"{len(checks)} correct; failures={failures}; "
        + client_transport.usage_summary()
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
