from __future__ import annotations

from typing import Any

from fpna_copilot.graph.ai_planner_graph import ask_ai_from_sqlite
from fpna_copilot.planners.deterministic_planner import ask_deterministic_from_sqlite


def normalize_fpna_result(
    *,
    result: dict[str, Any],
    mode: str,
    used_fallback: bool = False,
) -> dict[str, Any]:
    """
    Normalize AI and deterministic results into one common response shape.

    This lets FastAPI / UI / CopilotKit consume one structure regardless of mode.
    """

    return {
        "mode": mode,
        "used_fallback": used_fallback,
        "can_answer": bool(result.get("can_answer", False)),
        "answer": result.get("answer", ""),
        "tool_plan": result.get("tool_plan", []),
        "tool_results": result.get("tool_results", []),
        "reflection": result.get("reflection", ""),
    }


def ask_fpna(
    question: str,
    *,
    ai_mode: bool = False,
    fallback_to_deterministic: bool = True,
) -> dict[str, Any]:
    """
    Main FP&A service entry point.

    AI OFF:
    - deterministic planner creates tool plan
    - approved tools calculate answer

    AI ON:
    - LangGraph AI planner creates tool plan
    - approved tools calculate answer

    Safety rule:
    AI never executes raw SQL or pandas.
    AI only selects approved finance tools.
    """

    question = str(question or "").strip()

    if not question:
        return {
            "mode": "ai" if ai_mode else "deterministic",
            "used_fallback": False,
            "can_answer": False,
            "answer": "Please ask a finance question.",
            "tool_plan": [],
            "tool_results": [],
            "reflection": "Empty question.",
        }

    if not ai_mode:
        result = ask_deterministic_from_sqlite(question)
        return normalize_fpna_result(
            result=result,
            mode="deterministic",
            used_fallback=False,
        )

    try:
        ai_result = ask_ai_from_sqlite(question)

        if ai_result.get("can_answer"):
            return normalize_fpna_result(
                result=ai_result,
                mode="ai",
                used_fallback=False,
            )

        if not fallback_to_deterministic:
            return normalize_fpna_result(
                result=ai_result,
                mode="ai",
                used_fallback=False,
            )

        deterministic_result = ask_deterministic_from_sqlite(question)

        normalized = normalize_fpna_result(
            result=deterministic_result,
            mode="deterministic",
            used_fallback=True,
        )

        normalized["reflection"] = (
            "AI mode could not answer, so deterministic fallback was used. "
            f"AI reflection: {ai_result.get('reflection', '')}"
        )

        return normalized

    except Exception as exc:
        if not fallback_to_deterministic:
            return {
                "mode": "ai",
                "used_fallback": False,
                "can_answer": False,
                "answer": "I don't know based on the loaded CT-Narrative SQLite data.",
                "tool_plan": [],
                "tool_results": [],
                "reflection": f"AI mode failed: {type(exc).__name__}: {exc}",
            }

        deterministic_result = ask_deterministic_from_sqlite(question)

        normalized = normalize_fpna_result(
            result=deterministic_result,
            mode="deterministic",
            used_fallback=True,
        )

        normalized["reflection"] = (
            "AI mode failed, so deterministic fallback was used. "
            f"AI error: {type(exc).__name__}: {exc}"
        )

        return normalized