from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from fpna_copilot.column_rules import UNIT
from fpna_copilot.store.sqlite_store import SQLiteStore, store
from fpna_copilot.utils import fmt_money, safe_snippet


PeriodType = Literal["in_month", "ytd"]
MetricName = Literal["revenue", "profit", "cash"]
VarianceDirection = Literal["absolute", "favourable", "adverse"]


def default_variance_scenario(period_type: PeriodType) -> str:
    """
    Default variance comparison based on strict CT-Narrative rules.

    In-month defaults to Actual vs LBE.
    YTD defaults to Actual vs Budget.
    """

    if period_type == "ytd":
        return "variance_budget"

    return "variance_lbe"


def default_comparator_scenario(period_type: PeriodType) -> tuple[str, str]:
    """
    Return the default scenario used as comparator.

    In-month: LBE
    YTD: Budget
    """

    if period_type == "ytd":
        return "budget", "Budget"

    return "lbe", "LBE"


def normalize_comparator(comparator: str | None) -> str | None:
    """
    Normalize comparator words from user/planner into internal names.

    Important business rule:
    - If user says prior / prior month in the current single CT-Narrative sheet,
      treat it as LBE for in-month.
    """

    if comparator is None:
        return None

    value = (
        str(comparator)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        "default": "default",
        "actual": "actual",
        "lbe": "lbe",
        "forecast": "lbe",
        "latest_best_estimate": "lbe",
        "prior": "prior",
        "previous": "prior",
        "prior_month": "prior_month",
        "previous_month": "prior_month",
        "last_month": "prior_month",
        "business_plan": "business_plan",
        "bp": "business_plan",
        "plan": "business_plan",
        "budget": "budget",
        "actual_2025": "actual_2025",
        "prior_year": "prior_year",
        "previous_year": "prior_year",
        "last_year": "prior_year",
        "py": "prior_year",
    }

    return aliases.get(value, value)


def comparator_mapping(
    *,
    period_type: PeriodType,
    comparator: str | None,
) -> dict[str, Any]:
    """
    Map user comparator words to strict CT-Narrative SQLite scenarios.

    In-month:
    - LBE uses lbe + variance_lbe
    - Prior / prior month also uses LBE in the current single sheet
    - Business Plan uses business_plan + variance_bp

    YTD:
    - Budget / Business Plan / LBE map to budget + variance_budget
      because YTD has Budget columns, not LBE or Business Plan columns.
    - Prior year / last year maps to actual_2025 + variance_actual_2025

    Later, once multiple monthly uploads exist, real prior-month comparison
    can be calculated from uploaded periods instead of using LBE.
    """

    comparator = normalize_comparator(comparator)

    if comparator in {None, "", "default"}:
        if period_type == "ytd":
            comparator = "budget"
        else:
            comparator = "lbe"

    if period_type == "in_month":
        if comparator in {"lbe", "forecast", "prior", "prior_month"}:
            return {
                "supported": True,
                "comparator_scenario": "lbe",
                "comparator_name": "LBE",
                "variance_scenario": "variance_lbe",
            }

        if comparator in {"business_plan", "budget", "bp", "plan"}:
            return {
                "supported": True,
                "comparator_scenario": "business_plan",
                "comparator_name": "Business Plan",
                "variance_scenario": "variance_bp",
            }

        return {
            "supported": False,
            "reason": f"Comparator '{comparator}' is not supported for in-month.",
        }

    if period_type == "ytd":
        if comparator in {
            "budget",
            "business_plan",
            "bp",
            "plan",
            "lbe",
            "forecast",
            "prior",
            "prior_month",
        }:
            return {
                "supported": True,
                "comparator_scenario": "budget",
                "comparator_name": "Budget",
                "variance_scenario": "variance_budget",
            }

        if comparator in {"actual_2025", "prior_year", "last_year", "previous_year", "py"}:
            return {
                "supported": True,
                "comparator_scenario": "actual_2025",
                "comparator_name": "Actual 2025",
                "variance_scenario": "variance_actual_2025",
            }

        return {
            "supported": False,
            "reason": f"Comparator '{comparator}' is not supported for YTD.",
        }

    return {
        "supported": False,
        "reason": f"Period type '{period_type}' is not supported.",
    }


def get_top_variance(
    *,
    metric: MetricName,
    period_type: PeriodType = "in_month",
    category: str | None = None,
    contract: str | None = None,
    top_n: int = 5,
    direction: VarianceDirection = "absolute",
    comparator: str | None = None,
    db_store: SQLiteStore = store,
) -> dict[str, Any]:
    """
    Return top variance rows from SQLite fact_finance.

    This reads normalized DB-style rows into pandas, then does calculation/ranking.

    Important:
    - AI should call this tool.
    - AI should not calculate numbers directly.
    """

    fact = db_store.read_table("fact_finance")

    if fact.empty:
        return {
            "can_answer": False,
            "answer": "No finance data is loaded in SQLite.",
            "data": [],
            "reflection": "fact_finance table is empty.",
        }

    mapping = comparator_mapping(period_type=period_type, comparator=comparator)

    if not mapping.get("supported"):
        return {
            "can_answer": False,
            "answer": "I don't know based on the loaded CT-Narrative SQLite data.",
            "data": [],
            "reflection": mapping.get("reason", "Unsupported comparator."),
        }

    comparator_scenario = mapping["comparator_scenario"]
    comparator_name = mapping["comparator_name"]
    variance_scenario = mapping["variance_scenario"]

    scoped = fact[
        (fact["period_type"] == period_type)
        & (fact["metric"] == metric)
    ].copy()

    if category:
        scoped = scoped[scoped["category"].str.lower() == category.lower()].copy()

    if contract:
        scoped = scoped[
            scoped["contract"].str.lower().str.contains(contract.lower(), na=False)
        ].copy()

    if scoped.empty:
        return {
            "can_answer": False,
            "answer": "No matching finance rows found for the requested scope.",
            "data": [],
            "reflection": "SQLite query returned no matching rows.",
        }

    index_cols = [
        "upload_id",
        "period",
        "period_type",
        "category",
        "contract",
        "metric",
        "comment",
        "excel_row",
    ]

    pivot = (
        scoped.pivot_table(
            index=index_cols,
            columns="scenario",
            values="value",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )

    needed = ["actual", comparator_scenario, variance_scenario]

    for col in needed:
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot["actual"] = pivot["actual"].astype(float)
    pivot["comparator_value"] = pivot[comparator_scenario].astype(float)
    pivot["variance"] = pivot[variance_scenario].astype(float)
    pivot["comparator_name"] = comparator_name

    if direction == "adverse":
        result = pivot.sort_values("variance", ascending=True)
    elif direction == "favourable":
        result = pivot.sort_values("variance", ascending=False)
    else:
        result = (
            pivot.assign(abs_variance=pivot["variance"].abs())
            .sort_values("abs_variance", ascending=False)
        )

    result = result.head(top_n).copy()

    scope_label = ""
    if category:
        scope_label = f" for {category}"
    elif contract:
        scope_label = f" for {contract}"

    lines = [
        f"Top {len(result)} {period_type.replace('_', ' ')} {metric} variance item(s){scope_label} ({UNIT}):"
    ]

    output_rows: list[dict[str, Any]] = []

    for _, row in result.iterrows():
        output_row = {
            "category": row["category"],
            "contract": row["contract"],
            "period": row["period"],
            "period_type": row["period_type"],
            "metric": row["metric"],
            "actual": float(row["actual"]),
            "comparator_name": row["comparator_name"],
            "comparator_value": float(row["comparator_value"]),
            "variance": float(row["variance"]),
            "comment": row.get("comment", ""),
            "excel_row": int(row["excel_row"]),
        }
        output_rows.append(output_row)

        lines.append(
            f"- {row['contract']} | Category: {row['category']} | Metric: {str(row['metric']).title()} | "
            f"Actual: {fmt_money(float(row['actual']))} | "
            f"{row['comparator_name']}: {fmt_money(float(row['comparator_value']))} | "
            f"Variance vs {row['comparator_name']}: {fmt_money(float(row['variance']))} | "
            f"Comment: {safe_snippet(row.get('comment', '')) or 'No comment'}"
        )

    return {
        "can_answer": True,
        "answer": "\n".join(lines),
        "data": output_rows,
        "columns_used": {
            "source_table": "fact_finance",
            "period_type": period_type,
            "metric": metric,
            "actual_scenario": "actual",
            "comparator_scenario": comparator_scenario,
            "variance_scenario": variance_scenario,
        },
        "reflection": (
            "Calculated from normalized SQLite fact_finance rows. "
            "The ranking still uses pandas for trusted calculation, not the LLM."
        ),
    }


def get_actual_vs_comparator(
    *,
    metric: MetricName,
    period_type: PeriodType = "in_month",
    comparator: str | None = None,
    category: str | None = None,
    contract: str | None = None,
    db_store: SQLiteStore = store,
) -> dict[str, Any]:
    """
    Return actual vs comparator for a metric, period, and scope.

    Examples:
    - Tamasuk in-month revenue vs LBE
    - Tamasuk in-month revenue vs prior
    - Tamasuk in-month revenue vs Business Plan
    - Tamasuk YTD revenue vs Budget
    """

    mapping = comparator_mapping(period_type=period_type, comparator=comparator)

    if not mapping.get("supported"):
        return {
            "can_answer": False,
            "answer": "I don't know based on the loaded CT-Narrative SQLite data.",
            "data": [],
            "reflection": mapping.get("reason", "Unsupported comparator."),
        }

    comparator_scenario = mapping["comparator_scenario"]
    comparator_name = mapping["comparator_name"]
    variance_scenario = mapping["variance_scenario"]

    fact = db_store.read_table("fact_finance")

    if fact.empty:
        return {
            "can_answer": False,
            "answer": "No finance data is loaded in SQLite.",
            "data": [],
            "reflection": "fact_finance table is empty.",
        }

    scoped = fact[
        (fact["period_type"] == period_type)
        & (fact["metric"] == metric)
    ].copy()

    if category:
        scoped = scoped[scoped["category"].str.lower() == category.lower()].copy()

    if contract:
        scoped = scoped[
            scoped["contract"].str.lower().str.contains(contract.lower(), na=False)
        ].copy()

    if scoped.empty:
        return {
            "can_answer": False,
            "answer": "No matching finance rows found for the requested scope.",
            "data": [],
            "reflection": "SQLite query returned no matching rows.",
        }

    index_cols = [
        "upload_id",
        "period",
        "period_type",
        "category",
        "contract",
        "metric",
        "comment",
        "excel_row",
    ]

    pivot = (
        scoped.pivot_table(
            index=index_cols,
            columns="scenario",
            values="value",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )

    for col in ["actual", comparator_scenario, variance_scenario]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    grouped = (
        pivot.groupby(
            ["period", "period_type", "category", "contract", "metric"],
            dropna=False,
        )
        .agg(
            actual=("actual", "sum"),
            comparator_value=(comparator_scenario, "sum"),
            variance=(variance_scenario, "sum"),
            comment=(
                "comment",
                lambda values: " | ".join(
                    [str(value) for value in values if str(value).strip()]
                )[:500],
            ),
            row_count=("excel_row", "count"),
        )
        .reset_index()
    )

    scope_label = ""
    if contract:
        scope_label = f" for {contract}"
    elif category:
        scope_label = f" for {category}"

    lines = [
        f"{period_type.replace('_', ' ').title()} {metric} actual vs {comparator_name}{scope_label} ({UNIT}):"
    ]

    output_rows: list[dict[str, Any]] = []

    for _, row in grouped.iterrows():
        output_row = {
            "period": row["period"],
            "period_type": row["period_type"],
            "category": row["category"],
            "contract": row["contract"],
            "metric": row["metric"],
            "actual": float(row["actual"]),
            "comparator_name": comparator_name,
            "comparator_value": float(row["comparator_value"]),
            "variance": float(row["variance"]),
            "comment": row.get("comment", ""),
            "row_count": int(row["row_count"]),
        }
        output_rows.append(output_row)

        lines.append(
            f"- {row['contract']} | Category: {row['category']} | "
            f"Actual: {fmt_money(float(row['actual']))} | "
            f"{comparator_name}: {fmt_money(float(row['comparator_value']))} | "
            f"Variance: {fmt_money(float(row['variance']))} | "
            f"Comment: {safe_snippet(row.get('comment', '')) or 'No comment'}"
        )

    return {
        "can_answer": True,
        "answer": "\n".join(lines),
        "data": output_rows,
        "columns_used": {
            "source_table": "fact_finance",
            "period_type": period_type,
            "metric": metric,
            "actual_scenario": "actual",
            "comparator_scenario": comparator_scenario,
            "variance_scenario": variance_scenario,
        },
        "reflection": (
            "Calculated actual vs comparator from normalized SQLite fact_finance rows. "
            "Pandas performed the calculation after reading trusted SQLite data."
        ),
    }