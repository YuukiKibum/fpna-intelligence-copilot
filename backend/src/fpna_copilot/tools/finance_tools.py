from __future__ import annotations

from typing import Any, Callable

from fpna_copilot.finance_engine.sqlite_metrics import (
    get_actual_vs_comparator,
    get_top_variance,
)
from fpna_copilot.models import FinanceToolResult


FinanceToolFunction = Callable[..., dict[str, Any]]


SUPPORTED_METRICS = {"revenue", "profit", "cash"}
SUPPORTED_PERIOD_TYPES = {"in_month", "ytd"}
SUPPORTED_DIRECTIONS = {"absolute", "favourable", "adverse"}


def validate_metric(metric: str) -> str | None:
    """
    Validate finance metric.
    """

    metric = str(metric).strip().lower()

    if metric not in SUPPORTED_METRICS:
        return None

    return metric


def validate_period_type(period_type: str) -> str | None:
    """
    Validate period type.
    """

    period_type = str(period_type).strip().lower()

    if period_type not in SUPPORTED_PERIOD_TYPES:
        return None

    return period_type


def validate_direction(direction: str) -> str:
    """
    Validate variance direction.
    """

    direction = str(direction).strip().lower()

    if direction not in SUPPORTED_DIRECTIONS:
        return "absolute"

    return direction


def top_variance_tool(
    *,
    metric: str,
    period_type: str = "in_month",
    category: str | None = None,
    contract: str | None = None,
    top_n: int = 5,
    direction: str = "absolute",
    comparator: str | None = None,
) -> dict[str, Any]:
    """
    Tool for ranking top variance items from the normalized SQLite finance table.

    Examples:
    - top 5 revenue variance in UAE
    - top 10 cash variance
    - top 3 positive profit variance
    - worst YTD revenue variance
    - top revenue variance vs business plan
    """

    safe_metric = validate_metric(metric)

    if safe_metric is None:
        return {
            "can_answer": False,
            "answer": "Unsupported metric. Supported metrics are revenue, profit, and cash.",
            "data": [],
            "reflection": f"Rejected unsupported metric: {metric}",
        }

    safe_period_type = validate_period_type(period_type)

    if safe_period_type is None:
        return {
            "can_answer": False,
            "answer": "Unsupported period type. Supported period types are in_month and ytd.",
            "data": [],
            "reflection": f"Rejected unsupported period_type: {period_type}",
        }

    safe_top_n = max(1, min(100, int(top_n)))
    safe_direction = validate_direction(direction)

    return get_top_variance(
        metric=safe_metric,  # type: ignore[arg-type]
        period_type=safe_period_type,  # type: ignore[arg-type]
        category=category,
        contract=contract,
        top_n=safe_top_n,
        direction=safe_direction,  # type: ignore[arg-type]
        comparator=comparator,
    )


def actual_vs_comparator_tool(
    *,
    metric: str,
    period_type: str = "in_month",
    comparator: str | None = None,
    category: str | None = None,
    contract: str | None = None,
) -> dict[str, Any]:
    """
    Tool for actual vs comparator analysis.

    Examples:
    - Tamasuk in-month revenue vs LBE
    - Tamasuk in-month revenue vs prior
    - Tamasuk in-month revenue vs Business Plan
    - Tamasuk YTD revenue vs Budget
    - KSA YTD cash vs Budget
    """

    safe_metric = validate_metric(metric)

    if safe_metric is None:
        return {
            "can_answer": False,
            "answer": "Unsupported metric. Supported metrics are revenue, profit, and cash.",
            "data": [],
            "reflection": f"Rejected unsupported metric: {metric}",
        }

    safe_period_type = validate_period_type(period_type)

    if safe_period_type is None:
        return {
            "can_answer": False,
            "answer": "Unsupported period type. Supported period types are in_month and ytd.",
            "data": [],
            "reflection": f"Rejected unsupported period_type: {period_type}",
        }

    return get_actual_vs_comparator(
        metric=safe_metric,  # type: ignore[arg-type]
        period_type=safe_period_type,  # type: ignore[arg-type]
        comparator=comparator,
        category=category,
        contract=contract,
    )


FINANCE_TOOL_REGISTRY: dict[str, FinanceToolFunction] = {
    "top_variance": top_variance_tool,
    "actual_vs_comparator": actual_vs_comparator_tool,
}


def list_finance_tools() -> list[dict[str, Any]]:
    """
    Return metadata about available finance tools.

    Later, LangGraph / AI planner can use this to understand which tools exist.
    """

    return [
        {
            "name": "top_variance",
            "description": "Rank top variance items by metric, period, category/contract scope, comparator, and variance direction.",
            "args": {
                "metric": "revenue | profit | cash",
                "period_type": "in_month | ytd",
                "category": "Optional Column B category/country such as UAE, KSA, Qatar",
                "contract": "Optional Column C contract name such as Tamasuk",
                "top_n": "Number of rows to return",
                "direction": "absolute | favourable | adverse",
                "comparator": "Optional: lbe | prior | business_plan | budget | actual_2025 | prior_year",
            },
        },
        {
            "name": "actual_vs_comparator",
            "description": "Return actual vs comparator for one metric, period, category/contract scope.",
            "args": {
                "metric": "revenue | profit | cash",
                "period_type": "in_month | ytd",
                "comparator": "lbe | prior | business_plan | budget | actual_2025 | prior_year",
                "category": "Optional Column B category/country such as UAE, KSA, Qatar",
                "contract": "Optional Column C contract name such as Tamasuk",
            },
        },
    ]


def execute_finance_tool(
    tool_name: str,
    args: dict[str, Any] | None = None,
) -> FinanceToolResult:
    """
    Execute one approved finance tool.

    This is the safe gateway:
    - deterministic planner will call this
    - LangGraph AI planner will call this
    - UI/API can call this

    The LLM should never execute raw pandas or SQL directly.
    """

    args = args or {}

    tool = FINANCE_TOOL_REGISTRY.get(tool_name)

    if tool is None:
        return FinanceToolResult(
            tool_name=tool_name,
            success=False,
            data={},
            error=f"Unknown finance tool: {tool_name}",
        )

    try:
        result = tool(**args)

        can_answer = bool(result.get("can_answer", True))

        return FinanceToolResult(
            tool_name=tool_name,
            success=can_answer,
            data=result,
            error=None if can_answer else result.get("reflection"),
        )
    except Exception as exc:
        return FinanceToolResult(
            tool_name=tool_name,
            success=False,
            data={},
            error=f"{type(exc).__name__}: {exc}",
        )


def execute_finance_tool_plan(
    tool_plan: list[dict[str, Any]],
) -> list[FinanceToolResult]:
    """
    Execute multiple finance tool calls in order.

    Example tool_plan:
    [
        {
            "tool_name": "actual_vs_comparator",
            "args": {
                "metric": "revenue",
                "period_type": "in_month",
                "comparator": "prior",
                "contract": "Tamasuk"
            }
        },
        {
            "tool_name": "actual_vs_comparator",
            "args": {
                "metric": "revenue",
                "period_type": "in_month",
                "comparator": "business_plan",
                "contract": "Tamasuk"
            }
        }
    ]
    """

    results: list[FinanceToolResult] = []

    for call in tool_plan:
        tool_name = call.get("tool_name", "")
        args = call.get("args", {})
        results.append(execute_finance_tool(tool_name, args))

    return results