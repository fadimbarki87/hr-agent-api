"""Evaluate the production structured planner on the balanced route corpus."""

import sys
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment
from route_eval_cases import ROUTE_EVAL_CASES

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.planner import PLAN_AUDIT_SYSTEM_PROMPT, plan_question
from hr_agent.query_builder import QueryBuildError, build_query
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 240


class RecordingClient(AzureOpenAIClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = []

    def chat_json(self, system_prompt, user_prompt, *, max_tokens):
        payload = super().chat_json(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
        )
        stage = (
            "auditor"
            if system_prompt == PLAN_AUDIT_SYSTEM_PROMPT
            else "planner"
        )
        self.diagnostics.append((stage, payload))
        return payload


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

    transport = AzureUsageTransport(MAX_AZURE_CALLS)
    client = RecordingClient(Settings.from_environment(), transport=transport)
    cases = list(ROUTE_EVAL_CASES)
    if len(sys.argv) == 3 and sys.argv[1] == "--limit":
        cases = ROUTE_EVAL_CASES[: int(sys.argv[2])]
    elif len(sys.argv) == 3 and sys.argv[1] == "--indices":
        selected = {int(value) for value in sys.argv[2].split(",")}
        cases = [
            case
            for index, case in enumerate(ROUTE_EVAL_CASES, start=1)
            if index in selected
        ]
        if len(cases) != len(selected):
            print("One or more requested route indices do not exist")
            return 2
    elif len(sys.argv) == 3 and sys.argv[1] == "--question":
        cases = [(sys.argv[2], "sql_only")]

    def evaluate(case):
        question, expected_route = case
        plan = plan_question(client, question)
        actual_route = plan.route if plan is not None else None
        invalid_query = None
        if plan is not None and plan.supported and plan.query is not None:
            try:
                build_query(
                    plan.query,
                    semantic_candidate_ids=[1]
                    if plan.route == "review_semantic_plus_sql"
                    else None,
                )
            except QueryBuildError as error:
                invalid_query = str(error)
        return question, expected_route, actual_route, invalid_query, plan

    results = []
    for completed, case in enumerate(cases, start=1):
        results.append(evaluate(case))
        if len(cases) > 1:
            time.sleep(0.75)
        if completed % 20 == 0:
            print(f"Planned {completed}/{len(cases)} questions", flush=True)

    mismatches = [result for result in results if result[1] != result[2]]
    invalid_queries = [
        (question, error, plan)
        for question, _expected, _actual, error, plan in results
        if error is not None
    ]
    print(
        "Azure structured-plan evaluation: "
        f"routes={len(results) - len(mismatches)}/{len(results)} correct; "
        f"invalid_queries={len(invalid_queries)}; "
        + transport.usage_summary()
    )
    for question, expected, actual, _error, plan in mismatches:
        printable_question = question.encode(
            "ascii",
            errors="backslashreplace",
        ).decode("ascii")
        print(
            f"ROUTE MISMATCH expected={expected} actual={actual}: "
            f"{printable_question}; "
            f"plan={plan!r}"
        )
    for question, error, plan in invalid_queries:
        printable_question = question.encode(
            "ascii",
            errors="backslashreplace",
        ).decode("ascii")
        print(f"INVALID QUERY {error}: {printable_question}; plan={plan!r}")
    if mismatches or invalid_queries:
        for stage, payload in client.diagnostics:
            print(f"DIAGNOSTIC {stage}: {ascii(payload)}")
    return 1 if mismatches or invalid_queries else 0


if __name__ == "__main__":
    sys.exit(main())
