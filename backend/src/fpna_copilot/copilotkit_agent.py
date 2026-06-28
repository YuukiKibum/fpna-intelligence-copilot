from __future__ import annotations

import json
import math
import os
from typing import Any, TypedDict

from copilotkit import CopilotKitMiddleware, CopilotKitState
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool

from fpna_copilot.finance_engine.copilot_service import ask_fpna

load_dotenv()


class AgentState(CopilotKitState):
    pass


class AgentContext(TypedDict, total=False):
    pass


def _model_name() -> str:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

    if ":" in model:
        return model

    return f"openai:{model}"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    return value


def _extract_rows(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for result in tool_results or []:
        data = result.get("data") or {}

        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                rows.extend(data["data"])
            elif isinstance(data.get("rows"), list):
                rows.extend(data["rows"])
            elif isinstance(data.get("result"), list):
                rows.extend(data["result"])
            else:
                rows.append(data)

        elif isinstance(data, list):
            rows.extend(data)

    return [row for row in rows if isinstance(row, dict)]


def _extract_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []

    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(str(key))

    return columns


def _pick_chart_keys(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    if not rows:
        return None, None

    first_row = rows[0]

    x_candidates = [
        "contract",
        "category",
        "metric",
        "period_type",
        "comparator_name",
    ]

    y_candidates = [
        "variance",
        "actual",
        "comparator_value",
        "value",
    ]

    x_key = next((key for key in x_candidates if key in first_row), None)

    y_key = next(
        (
            key
            for key in y_candidates
            if isinstance(first_row.get(key), int | float)
            and not isinstance(first_row.get(key), bool)
        ),
        None,
    )

    if x_key is None:
        for key, value in first_row.items():
            if isinstance(value, str):
                x_key = key
                break

    if y_key is None:
        for key, value in first_row.items():
            if key == "excel_row":
                continue

            if isinstance(value, int | float) and not isinstance(value, bool):
                y_key = key
                break

    return x_key, y_key


def _build_finance_result(
    *,
    question: str,
    service_result: dict[str, Any],
) -> dict[str, Any]:
    tool_results = service_result.get("tool_results") or []
    rows = _extract_rows(tool_results)
    columns = _extract_columns(rows)

    answer_text = str(service_result.get("answer") or "")
    reflection = str(service_result.get("reflection") or "")
    mode = str(service_result.get("mode") or "deterministic")

    metrics = [
        {
            "label": "Mode",
            "value": mode.title(),
            "direction": "neutral",
        },
        {
            "label": "Rows returned",
            "value": len(rows),
            "direction": "neutral",
        },
    ]

    charts: list[dict[str, Any]] = []

    x_key, y_key = _pick_chart_keys(rows)

    if x_key and y_key and len(rows) >= 2:
        chart_data = []

        for row in rows[:15]:
            x_value = row.get(x_key)
            y_value = row.get(y_key)

            if isinstance(y_value, int | float) and x_value is not None:
                chart_data.append(
                    {
                        x_key: str(x_value),
                        y_key: float(y_value),
                    }
                )

        if chart_data:
            charts.append(
                {
                    "title": f"{str(y_key).replace('_', ' ').title()} by {str(x_key).replace('_', ' ').title()}",
                    "chart_type": "bar",
                    "x_key": x_key,
                    "y_key": y_key,
                    "data": chart_data,
                }
            )

    tables = []

    if rows:
        tables.append(
            {
                "title": "Finance Detail",
                "columns": columns,
                "rows": rows[:50],
            }
        )

    assumptions = [
        "Values are calculated by approved backend finance tools.",
        "The AI selects tools and explains results; it does not calculate finance numbers directly.",
    ]

    if reflection:
        assumptions.append(reflection)

    return _json_safe(
        {
            "title": f"FP&A Analysis: {question}",
            "summary": answer_text,
            "metrics": metrics,
            "tables": tables,
            "charts": charts,
            "assumptions": assumptions,
            "follow_up_questions": [
                "Show the same view for YTD.",
                "Show only adverse movements.",
                "Compare revenue, profit, and cash.",
                "Show top favourable and adverse variances.",
            ],
            "raw": {
                "question": question,
                "service_result": service_result,
            },
        }
    )


@tool
def fetch_fpna_result(question: str, ai_mode: bool = True) -> str:
    """
    Fetch FP&A finance results from the approved backend finance service.

    Use this tool for all questions about revenue, profit, cash, actuals,
    LBE, budget, business plan, prior month, YTD, in-month, contracts,
    categories, and variances.

    The returned JSON is already shaped for the frontend tool show_finance_result.
    """

    service_result = ask_fpna(
        question=question,
        ai_mode=ai_mode,
    )

    finance_result = _build_finance_result(
        question=question,
        service_result=service_result,
    )

    return json.dumps(finance_result, ensure_ascii=False)


FPNA_COPILOT_SYSTEM_PROMPT = """
You are an FP&A Intelligence Copilot.

Your job:
- Understand the user's finance question.
- Use fetch_fpna_result to get approved backend finance data.
- Never calculate finance numbers yourself.
- Never invent finance values.
- After fetching the result, call the frontend tool named show_finance_result.

Important:
- Do not return ui_spec.
- Do not generate React or JSX.
- Do not describe component layouts.
- The frontend owns generative UI rendering.
- The backend owns finance data and calculations.

Workflow:
1. Call fetch_fpna_result with the user's exact question.
2. Parse the JSON returned by fetch_fpna_result.
3. Call the frontend tool show_finance_result with that JSON object.
4. Then provide a short plain-English confirmation.
"""


fpna_agent = create_agent(
    model=_model_name(),
    tools=[fetch_fpna_result],
    middleware=[CopilotKitMiddleware()],
    state_schema=AgentState,
    context_schema=AgentContext,
    system_prompt=FPNA_COPILOT_SYSTEM_PROMPT,
)