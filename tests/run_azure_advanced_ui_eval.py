"""Validate the promoted advanced SQL UI examples without building embeddings."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from run_azure_blind_holdout import validate_case
from run_azure_sql_stress import expected_plan, execute_canonical, selection_keys
from sql_stress_cases import SQL_STRESS_CASES
from ui_eval_cases import UI_EVAL_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.database import HRDatabase
from hr_agent.planner import plan_question
from hr_agent.settings import Settings


INTENT_IDS = (1, 7, 9, 3)
UI_CASES = UI_EVAL_CASES[8:12]


def main() -> int:
    missing = configure_private_environment(
        {
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_OPENAI_API_VERSION",
            "AZURE_OPENAI_API_KEY",
        }
    )
    if missing:
        print("Missing required configuration: " + ", ".join(missing))
        return 2

    source_cases = {
        item["intent"]: item
        for item in SQL_STRESS_CASES
        if item["language"] == "en"
    }
    transport = AzureUsageTransport(24)
    client = AzureOpenAIClient(Settings.from_environment(), transport=transport)
    database = HRDatabase.from_project_files()
    failures = []

    for position, (intent_id, ui_case) in enumerate(
        zip(INTENT_IDS, UI_CASES, strict=True),
        start=1,
    ):
        expected = dict(source_cases[intent_id])
        expected["question"] = ui_case.question
        plan = plan_question(client, ui_case.question)
        errors = validate_case(expected, plan)

        expected_query = expected_plan(expected).query
        assert expected_query is not None
        keys = selection_keys(expected_query)
        expected_rows = execute_canonical(database, expected_query, keys)
        actual_rows = None
        if plan is not None and plan.supported and plan.query is not None:
            actual_rows = execute_canonical(database, plan.query, keys)
        result_ok = actual_rows == expected_rows
        if errors or not result_ok:
            failures.append((position, errors, result_ok, plan))
        print(
            f"{position} exact={not errors} result={result_ok} "
            f"route={plan.route if plan else None}",
            flush=True,
        )

    print(
        f"Advanced SQL UI evaluation: {4 - len(failures)}/4; "
        + transport.usage_summary()
    )
    for position, errors, result_ok, plan in failures:
        print(
            f"MISMATCH {position}: errors={errors!r} "
            f"result_ok={result_ok}; plan={plan!r}"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
