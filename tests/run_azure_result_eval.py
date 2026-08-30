"""End-to-end live evaluation for every selectable website example."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from ui_eval_cases import UI_EVAL_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.service import HRAgentService
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 100


def ui_questions() -> list[str]:
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    return re.findall(r"<li>(.*?)</li>", html)


def employee_name_map(service: HRAgentService) -> dict[tuple[str, str], int]:
    columns, rows = service.database.execute(
        "SELECT employee_id, first_name, last_name FROM employees"
    )
    positions = {column: index for index, column in enumerate(columns)}
    return {
        (
            str(row[positions["first_name"]]),
            str(row[positions["last_name"]]),
        ): int(row[positions["employee_id"]])
        for row in rows
    }


def result_employee_ids(result: dict | None, names: dict) -> set[int] | None:
    if result is None:
        return None
    columns = result["columns"]
    rows = result["rows"]
    if "employee_id" in columns:
        return {int(row["employee_id"]) for row in rows}
    if "first_name" in columns and "last_name" in columns:
        return {
            names[(row["first_name"], row["last_name"])]
            for row in rows
        }
    return None


def scalar_value(result: dict | None) -> int | float | str | None:
    if result is None or result["row_count"] != 1 or len(result["columns"]) != 1:
        return None
    value = result["rows"][0][result["columns"][0]]
    if not isinstance(value, str):
        return value
    try:
        is_decimal = any(mark in value.lower() for mark in (".", "e"))
        return float(value) if is_decimal else int(value)
    except ValueError:
        return value


def main() -> int:
    required = {
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    }
    missing = configure_private_environment(required)
    if missing:
        print("Missing required configuration: " + ", ".join(missing))
        return 2

    questions = ui_questions()
    expected_questions = [case.question for case in UI_EVAL_CASES]
    if questions != expected_questions:
        print("Website examples do not match the typed UI evaluation contract")
        return 2

    transport = AzureUsageTransport(MAX_AZURE_CALLS)
    settings = Settings.from_environment()
    client = AzureOpenAIClient(settings, transport=transport)
    print("Building raw-review semantic index...", flush=True)
    service = HRAgentService(settings, client=client)
    print(
        f"Semantic index ready={service.retriever.ready} "
        f"backend={service.retriever.backend}; {transport.usage_summary()}",
        flush=True,
    )
    if not service.retriever.ready:
        return 2
    if len(sys.argv) == 2 and sys.argv[1] == "--index-only":
        return 0

    indexed_cases = list(enumerate(UI_EVAL_CASES, start=1))
    if len(sys.argv) == 3 and sys.argv[1] == "--indices":
        selected = {int(value) for value in sys.argv[2].split(",")}
        indexed_cases = [item for item in indexed_cases if item[0] in selected]
        if len(indexed_cases) != len(selected):
            print("One or more requested UI indices do not exist")
            return 2

    names = employee_name_map(service)
    failures = []
    for index, expected in indexed_cases:
        traced = service.answer_with_trace(
            expected.question,
            use_ai_formulation=False,
        )
        evidence = traced["evidence"]
        result = evidence.get("result")
        actual_semantic_ids = set(evidence.get("semantic_candidate_ids") or [])
        actual_final_ids = result_employee_ids(result, names)
        actual_row_count = result["row_count"] if result is not None else None
        actual_scalar = scalar_value(result)
        print(
            f"{index:02} route={evidence['route_used']} "
            f"status={evidence['status']} scope={evidence['semantic_scope']} "
            f"rows={actual_row_count} scalar={actual_scalar} "
            f"semantic={sorted(actual_semantic_ids)} final="
            f"{sorted(actual_final_ids) if actual_final_ids is not None else None}",
            flush=True,
        )

        checks = {
            "route": (expected.route, evidence["route_used"]),
            "language": (expected.language, evidence.get("answer_language")),
            "status": (expected.status, evidence["status"]),
            "unsupported_category": (
                expected.unsupported_category,
                evidence.get("unsupported_category"),
            ),
            "scope": (expected.semantic_scope, evidence["semantic_scope"]),
        }
        for label, (wanted, actual) in checks.items():
            if wanted != actual:
                failures.append(
                    f"{index:02} {label} expected={wanted!r} actual={actual!r}"
                )
        if expected.row_count is not None and actual_row_count != expected.row_count:
            failures.append(
                f"{index:02} rows expected={expected.row_count} "
                f"actual={actual_row_count}"
            )
        if expected.scalar_value is not None and actual_scalar != expected.scalar_value:
            failures.append(
                f"{index:02} scalar expected={expected.scalar_value} "
                f"actual={actual_scalar}"
            )
        if (
            expected.semantic_ids is not None
            and actual_semantic_ids != set(expected.semantic_ids)
        ):
            failures.append(
                f"{index:02} semantic expected={sorted(expected.semantic_ids)} "
                f"actual={sorted(actual_semantic_ids)}"
            )
        if (
            expected.final_ids is not None
            and actual_final_ids != set(expected.final_ids)
        ):
            failures.append(
                f"{index:02} final expected={sorted(expected.final_ids)} "
                f"actual={sorted(actual_final_ids) if actual_final_ids is not None else None}"
            )

    failed_cases = {int(failure[:2]) for failure in failures}
    print(
        "Azure website-example evaluation: "
        f"{len(indexed_cases) - len(failed_cases)}/{len(indexed_cases)} "
        f"cases correct; failed_checks={len(failures)}; "
        + transport.usage_summary()
    )
    for failure in failures:
        print("MISMATCH " + failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
