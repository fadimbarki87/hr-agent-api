"""Capped live evaluation for classified and grounded boundary responses."""

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure_test_support import AzureUsageTransport, configure_private_environment

from hr_agent.azure_client import AzureOpenAIClient
from hr_agent.localization import UNSUPPORTED_MSG
from hr_agent.service import HRAgentService
from hr_agent.settings import Settings


MAX_AZURE_CALLS = 50


@dataclass(frozen=True)
class BoundaryCase:
    question: str
    category: str
    language: str


CASES = (
    BoundaryCase("What about them?", "vague", "en"),
    BoundaryCase("Was ist mit ihnen?", "vague", "de"),
    BoundaryCase(
        "What will the weather be in Paris tomorrow?",
        "out_of_scope",
        "en",
    ),
    BoundaryCase(
        "¿Puedes recomendar una receta para la cena?",
        "out_of_scope",
        "es",
    ),
    BoundaryCase(
        "What is the company's parental-leave policy?",
        "unavailable_data",
        "en",
    ),
    BoundaryCase(
        "ما هي مزايا التأمين الصحي التي تقدمها الشركة؟",
        "unavailable_data",
        "ar",
    ),
    BoundaryCase(
        "Increase every employee's salary by five percent.",
        "unsupported_operation",
        "en",
    ),
    BoundaryCase(
        "Supprime toutes les absences enregistrées.",
        "unsupported_operation",
        "fr",
    ),
)


class UnusedRetriever:
    ready = False
    backend = "unused"


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
    settings = Settings.from_environment()
    client = AzureOpenAIClient(settings, transport=transport)
    service = HRAgentService(
        settings,
        client=client,
        retriever=UnusedRetriever(),
    )

    failures = []
    for index, case in enumerate(CASES, start=1):
        traced = service.answer_with_trace(
            case.question,
            use_ai_formulation=True,
        )
        evidence = traced["evidence"]
        checks = {
            "status": evidence["status"] == "unsupported",
            "category": evidence["unsupported_category"] == case.category,
            "language": evidence["answer_language"] == case.language,
            "classification": (
                evidence["classification_source"] == "audited_azure_plan"
            ),
            "guidance": (
                evidence["guidance_source"] == "azure_grounded_guidance"
            ),
            "no_route": evidence["route_used"] == "none",
            "no_query": not evidence["sql"] and evidence["result"] is None,
            "schema_evidence": bool(evidence["available_data"]),
            "helpful_answer": bool(traced["answer"])
            and traced["answer"] != UNSUPPORTED_MSG,
        }
        failed = [label for label, passed in checks.items() if not passed]
        printable_answer = traced["answer"].encode(
            "ascii",
            errors="backslashreplace",
        ).decode("ascii")
        print(
            f"{index:02} expected={case.category}/{case.language} "
            f"actual={evidence['unsupported_category']}/"
            f"{evidence['answer_language']} guidance="
            f"{evidence['guidance_source']} failed={failed}\n"
            f"   answer={printable_answer!r}",
            flush=True,
        )
        if failed:
            failures.append((index, failed))

    print(
        f"Unsupported-response evaluation: {len(CASES) - len(failures)}/"
        f"{len(CASES)} correct; failures={failures}; "
        + transport.usage_summary()
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
