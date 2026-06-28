from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# Old stable CT-Narrative engine models
# ============================================================

Metric = Literal["revenue", "profit", "cash"]
MetricOrAll = Literal["revenue", "profit", "cash", "all"]
Period = Literal["in_month", "ytd"]

QuestionType = Literal[
    "overview",
    "entity_search",
    "contract_details",
    "list_contracts",
    "ranking_variance",
    "ranking_actual",
    "lowest_actual",
    "total",
    "actual_vs_comparator",
    "category_breakdown",
    "comments",
    "unknown",
]

VarianceDirection = Literal["absolute", "favourable", "adverse"]
Comparator = Literal["lbe", "business_plan", "budget", "actual_2025"]
Confidence = Literal["high", "medium", "low"]


class QuerySpec(BaseModel):
    question: str
    question_type: QuestionType
    metric: MetricOrAll = "all"
    requested_metrics: list[Metric] | None = None
    period: Period = "in_month"
    requested_periods: list[Period] | None = None
    comparator: Comparator | None = None
    variance_direction: VarianceDirection = "absolute"
    top_n: int = 10
    scope_text: str | None = None
    group_by: Literal["category", "contract"] | None = None
    contract_query: str | None = None
    category_query: str | None = None


class AgentAnswer(BaseModel):
    can_answer: bool
    answer: str
    question_spec: QuerySpec | None = None
    columns_used: dict[str, Any] = Field(default_factory=dict)
    reflection: str
    confidence: Confidence
    rows_used: int = 0
    data: list[dict[str, Any]] = Field(default_factory=list)


# ============================================================
# Revamp models for SQLite + LangGraph + CopilotKit
# ============================================================

class FinanceFactRow(BaseModel):
    """
    One row in our database-like finance table.

    Later, this can easily become a real database table.
    """

    upload_id: str
    file_name: str | None = None
    sheet_name: str | None = None

    period: str | None = None
    year: int | None = None
    month: str | None = None

    entity_type: str | None = None
    entity_name: str | None = None

    contract: str | None = None
    category: str | None = None
    country: str | None = None
    sector: str | None = None

    metric: str
    scenario: str
    value: float

    currency: str | None = None
    unit: str | None = None
    comment: str | None = None
    excel_row: int | None = None


class FinanceQuery(BaseModel):
    """
    User question coming from the frontend or test API.
    """

    question: str
    ai_mode: bool = False


class FinanceToolCall(BaseModel):
    """
    A tool the system wants to run.

    In AI mode, LangGraph/LLM decides this.
    In deterministic mode, the rule-based planner decides this.
    """

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)


class FinanceToolResult(BaseModel):
    """
    Result returned by a trusted pandas/SQLite finance tool.
    """

    tool_name: str
    success: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None