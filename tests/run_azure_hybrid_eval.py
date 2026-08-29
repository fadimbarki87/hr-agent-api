"""End-to-end evaluation of every balanced hybrid review-plus-SQL question."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from route_eval_cases import HYBRID_QUESTIONS

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.service import HRAgentService
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 140

EXPECTED_SEMANTIC_IDS = {
    1: {1}, 2: {1}, 3: {4, 9}, 4: {2}, 5: {9}, 6: {1}, 7: {13},
    8: {5}, 9: {14}, 10: {3, 11}, 11: {4}, 12: set(), 13: {2, 4, 6}, 14: {2},
    15: {13, 15}, 16: {7}, 17: {12}, 18: {1, 14}, 19: {4, 6, 11},
    20: {10}, 21: {1}, 22: {3, 11}, 23: {4}, 24: {2}, 25: {9},
    26: {5}, 27: {14}, 28: set(), 29: {12}, 30: {1}, 31: {2},
    32: {4, 6, 11}, 33: {13, 15},
}

EXPECTED_FINAL_IDS = {
    1: {1}, 2: set(), 3: {4}, 4: {2}, 5: set(), 6: {1},
    8: {5}, 9: {14}, 10: {3}, 11: {4}, 12: set(), 13: {6}, 14: {2},
    15: set(), 16: set(), 17: {12}, 18: {1, 14}, 20: {10}, 21: {1},
    22: {3, 11}, 23: {4}, 24: {2}, 25: set(), 26: {5}, 27: {14},
    29: {12}, 30: {1}, 31: {2}, 32: {11}, 33: {13, 15},
}

EXPECTED_COUNTS = {7: 1, 19: 1, 28: 0}

# "Key contributor" is explicit for employee 6 and reasonably inferable from
# the documented impact of employees 2 and 4. The final salary-filtered answer
# remains exact; this tolerance records genuine semantic ambiguity.
AMBIGUOUS_SEMANTIC_IDS = {
    13: ({6}, {2, 4, 6}),
    27: ({14}, {2, 14}),
}

AMBIGUOUS_FINAL_IDS = {
    27: ({14}, {2, 14}),
}


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


def scalar_count(result: dict | None) -> int | None:
    if result is None or result["row_count"] != 1 or len(result["columns"]) != 1:
        return None
    return int(result["rows"][0][result["columns"][0]])


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

    transport = AzureUsageTransport(MAX_AZURE_CALLS)
    settings = Settings.from_environment()
    client = AzureOpenAIClient(settings, transport=transport)
    print("Building raw-review semantic index...", flush=True)
    service = HRAgentService(settings, client=client)
    if not service.retriever.ready:
        print("Semantic index is unavailable")
        return 2
    names = employee_name_map(service)
    indexed_questions = list(enumerate(HYBRID_QUESTIONS, start=1))
    if len(sys.argv) == 3 and sys.argv[1] == "--indices":
        selected = {int(value) for value in sys.argv[2].split(",")}
        indexed_questions = [
            item for item in indexed_questions if item[0] in selected
        ]
        if len(indexed_questions) != len(selected):
            print("One or more requested hybrid indices do not exist")
            return 2
    failures = []

    for index, question in indexed_questions:
        traced = service.answer_with_trace(question, use_ai_formulation=False)
        evidence = traced["evidence"]
        route = evidence["route_used"]
        semantic_ids = set(evidence.get("semantic_candidate_ids") or [])
        final_ids = result_employee_ids(evidence.get("result"), names)
        count = scalar_count(evidence.get("result")) if index in EXPECTED_COUNTS else None
        print(
            f"{index:02} route={route} status={evidence['status']} "
            f"semantic={sorted(semantic_ids)} final="
            f"{sorted(final_ids) if final_ids is not None else None} count={count} "
            f"semantic_scope={evidence.get('semantic_scope')!r} "
            f"semantic_query={evidence.get('semantic_query')!r} "
            f"sql_parameters={evidence.get('sql_parameters')!r} "
            f"sql={evidence.get('sql')!r}",
            flush=True,
        )

        if route != "review_semantic_plus_sql":
            failures.append(f"{index:02} route={route}")
            continue
        if index in AMBIGUOUS_SEMANTIC_IDS:
            required_ids, allowed_ids = AMBIGUOUS_SEMANTIC_IDS[index]
            if not required_ids.issubset(semantic_ids) or not semantic_ids.issubset(
                allowed_ids
            ):
                failures.append(
                    f"{index:02} semantic required={sorted(required_ids)} "
                    f"allowed={sorted(allowed_ids)} actual={sorted(semantic_ids)}"
                )
        elif semantic_ids != EXPECTED_SEMANTIC_IDS[index]:
            failures.append(
                f"{index:02} semantic expected={sorted(EXPECTED_SEMANTIC_IDS[index])} "
                f"actual={sorted(semantic_ids)}"
            )
        if index in EXPECTED_COUNTS:
            if count != EXPECTED_COUNTS[index]:
                failures.append(
                    f"{index:02} count expected={EXPECTED_COUNTS[index]} actual={count}"
                )
        elif index in AMBIGUOUS_FINAL_IDS:
            required_ids, allowed_ids = AMBIGUOUS_FINAL_IDS[index]
            if (
                final_ids is None
                or not required_ids.issubset(final_ids)
                or not final_ids.issubset(allowed_ids)
            ):
                failures.append(
                    f"{index:02} final required={sorted(required_ids)} "
                    f"allowed={sorted(allowed_ids)} actual="
                    f"{sorted(final_ids) if final_ids is not None else None}"
                )
        elif final_ids != EXPECTED_FINAL_IDS[index]:
            failures.append(
                f"{index:02} final expected={sorted(EXPECTED_FINAL_IDS[index])} "
                f"actual={sorted(final_ids) if final_ids is not None else None}"
            )

    failed_cases = {int(failure[:2]) for failure in failures}
    print(
        "Azure hybrid evaluation: "
        f"{len(indexed_questions) - len(failed_cases)}/{len(indexed_questions)} "
        f"cases correct; failed_checks={len(failures)}; "
        + transport.usage_summary()
    )
    for failure in failures:
        print("MISMATCH " + failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
