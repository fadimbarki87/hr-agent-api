"""Backward-compatible entry points for the HR agent service."""

from __future__ import annotations

from hr_agent.service import get_default_service


def hr_agent_with_trace(
    question: str,
    use_ai_formulation: bool = False,
) -> dict:
    return get_default_service().answer_with_trace(
        question,
        use_ai_formulation=use_ai_formulation,
    )


def hr_agent(question: str, use_ai_formulation: bool = False) -> str:
    return hr_agent_with_trace(
        question,
        use_ai_formulation=use_ai_formulation,
    )["answer"]


__all__ = ["hr_agent", "hr_agent_with_trace"]
