from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from fpna_copilot.tools.finance_tools import execute_finance_tool_plan

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    fuzz = None


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "fpna_copilot.db"


def _normalise_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _to_plain_dict(value: Any) -> Any:
    """Convert Pydantic models and nested values into plain Python objects."""

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    if isinstance(value, list):
        return [_to_plain_dict(item) for item in value]

    if isinstance(value, tuple):
        return [_to_plain_dict(item) for item in value]

    if isinstance(value, dict):
        return {key: _to_plain_dict(item) for key, item in value.items()}

    return value


def _db_exists(db_path: Path = DEFAULT_DB_PATH) -> bool:
    return db_path.exists() and db_path.is_file()


def _read_distinct_fact_values(
    column_name: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    if not _db_exists(db_path):
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(fact_finance)")
            columns = {row[1] for row in cursor.fetchall()}

            if column_name not in columns:
                return []

            cursor.execute(
                f"""
                SELECT DISTINCT {column_name}
                FROM fact_finance
                WHERE {column_name} IS NOT NULL
                  AND TRIM(CAST({column_name} AS TEXT)) != ''
                ORDER BY {column_name}
                """
            )

            return [str(row[0]) for row in cursor.fetchall() if row and row[0]]

    except Exception:
        return []


def _available_contracts() -> list[str]:
    return _read_distinct_fact_values("contract")


def _available_categories() -> list[str]:
    return _read_distinct_fact_values("category")


def _contains_contract_name(question: str, contract: str) -> bool:
    question_norm = _normalise_text(question)
    contract_norm = _normalise_text(contract)

    if not question_norm or not contract_norm:
        return False

    if contract_norm in question_norm:
        return True

    contract_compact = contract_norm.replace(" ", "")
    question_compact = question_norm.replace(" ", "")

    if len(contract_compact) >= 4 and contract_compact in question_compact:
        return True

    contract_tokens = [token for token in contract_norm.split() if len(token) >= 4]
    question_tokens = set(question_norm.split())

    if contract_tokens and all(token in question_tokens for token in contract_tokens):
        return True

    return False


def _detect_multiple_contracts(question: str) -> list[str]:
    """Detect every contract explicitly mentioned in the question."""

    contracts = _available_contracts()
    matched: list[str] = []

    for contract in contracts:
        if _contains_contract_name(question, contract):
            matched.append(contract)

    # Fuzzy rescue for near spellings like "Melabs" vs "MELABS".
    # Threshold is intentionally high to avoid accidental contract matches.
    if fuzz is not None:
        question_norm = _normalise_text(question)

        for contract in contracts:
            if contract in matched:
                continue

            contract_norm = _normalise_text(contract)

            if len(contract_norm) < 4:
                continue

            score = fuzz.partial_ratio(contract_norm, question_norm)

            if score >= 94:
                matched.append(contract)

    deduped: list[str] = []

    for contract in matched:
        if contract not in deduped:
            deduped.append(contract)

    return deduped

def _wants_all_contracts(question: str) -> bool:
    question_norm = _normalise_text(question)

    return any(
        phrase in question_norm
        for phrase in [
            "all contracts",
            "every contract",
            "each contract",
            "all contract",
            "contract wise",
            "contractwise",
            "by contract",
        ]
    )


def _detect_category(question: str) -> str | None:
    categories = _available_categories()
    question_norm = _normalise_text(question)

    for category in categories:
        category_norm = _normalise_text(category)

        if not category_norm:
            continue

        if category_norm in question_norm:
            return category

    if "uae" in question_norm or "united arab emirates" in question_norm:
        for category in categories:
            if _normalise_text(category) == "uae":
                return category

    if "ksa" in question_norm or "saudi" in question_norm:
        for category in categories:
            if _normalise_text(category) in {"ksa", "saudi arabia"}:
                return category

    return None


def _detect_metrics(question: str) -> list[str]:
    question_norm = _normalise_text(question)
    metrics: list[str] = []

    if "revenue" in question_norm or "rev" in question_norm:
        metrics.append("revenue")

    if (
        "trading profit" in question_norm
        or "profit" in question_norm
        or re.search(r"\btp\b", question_norm)
        or "uop" in question_norm
    ):
        metrics.append("profit")

    if "cash" in question_norm or "fcf" in question_norm or "free cash" in question_norm:
        metrics.append("cash")

    if not metrics:
        metrics.append("revenue")

    return _dedupe(metrics)


def _detect_period_types(question: str) -> list[str]:
    question_norm = _normalise_text(question)
    periods: list[str] = []

    has_in_month = any(
        phrase in question_norm
        for phrase in [
            "in month",
            "inmonth",
            "monthly",
            "ftm",
        ]
    )

    # Only treat plain "month" as in-month if it is not just part of
    # "prior month" / "previous month".
    if "month" in question_norm and not any(
        phrase in question_norm for phrase in ["prior month", "previous month"]
    ):
        has_in_month = True

    has_ytd = any(
        phrase in question_norm
        for phrase in [
            "ytd",
            "year to date",
            "year date",
        ]
    )

    if has_in_month:
        periods.append("in_month")

    if has_ytd:
        periods.append("ytd")

    if not periods:
        periods.append("in_month")

    return _dedupe(periods)


def _detect_comparators(question: str) -> list[str]:
    question_norm = _normalise_text(question)
    comparators: list[str] = []

    if (
        "prior month" in question_norm
        or "previous month" in question_norm
        or "prior" in question_norm
    ):
        comparators.append("prior")

    if "lbe" in question_norm:
        comparators.append("lbe")

    if (
        "business plan" in question_norm
        or re.search(r"\bbp\b", question_norm)
        or "plan" in question_norm
    ):
        comparators.append("business_plan")

    if "budget" in question_norm:
        comparators.append("budget")

    if (
        "prior year" in question_norm
        or "previous year" in question_norm
        or "last year" in question_norm
        or "actual 2025" in question_norm
        or "2025" in question_norm
    ):
        comparators.append("prior_year")

    if not comparators:
        comparators.append("default")

    return _dedupe(comparators)


def _comparator_for_period(comparator: str, period_type: str) -> str:
    """Map user comparator wording to the right CT-Narrative comparator.

    CT-Narrative rule:
    - In-month prior/prior month = LBE.
    - YTD prior month/LBE/business plan/budget = Budget.
    - YTD prior year/last year = Actual 2025.
    """

    comparator = comparator or "default"

    if period_type == "in_month":
        if comparator in {"prior", "lbe"}:
            return "prior"

        if comparator == "business_plan":
            return "business_plan"

        if comparator == "budget":
            return "business_plan"

        if comparator == "prior_year":
            return "default"

        return comparator

    if period_type == "ytd":
        if comparator in {"prior", "lbe", "business_plan", "budget"}:
            return "budget"

        if comparator == "prior_year":
            return "prior_year"

        return comparator

    return comparator


def _detect_limit(question: str) -> int:
    match = re.search(r"\btop\s+(\d+)\b", question.lower())

    if match:
        return max(1, min(25, int(match.group(1))))

    match = re.search(r"\bbottom\s+(\d+)\b", question.lower())

    if match:
        return max(1, min(25, int(match.group(1))))

    return 5


def _is_top_or_ranked_question(question: str) -> bool:
    question_norm = _normalise_text(question)

    return any(
        phrase in question_norm
        for phrase in [
            "top",
            "bottom",
            "highest",
            "lowest",
            "largest",
            "rank",
            "ranking",
        ]
    )


def _detect_direction(question: str) -> str:
    question_norm = _normalise_text(question)

    if any(
        phrase in question_norm
        for phrase in [
            "adverse",
            "negative",
            "unfavourable",
            "unfavorable",
            "loss",
            "lowest",
            "bottom",
        ]
    ):
        return "adverse"

    if any(
        phrase in question_norm
        for phrase in [
            "absolute",
            "largest",
            "biggest",
            "movement",
        ]
    ):
        return "absolute"

    return "favourable"


def _dedupe(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []

    for item in items:
        if item not in deduped:
            deduped.append(item)

    return deduped


def _dedupe_tool_plan(tool_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []

    for item in tool_plan:
        tool_name = item.get("tool_name")
        args = item.get("args") or {}

        key = repr(
            (
                tool_name,
                args.get("metric"),
                args.get("period_type"),
                args.get("comparator"),
                args.get("category"),
                args.get("contract"),
                args.get("direction"),
                args.get("limit"),
            )
        )

        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


def build_deterministic_tool_plan(question: str) -> list[dict[str, Any]]:
    metrics = _detect_metrics(question)
    period_types = _detect_period_types(question)
    comparators = _detect_comparators(question)
    category = _detect_category(question)

    wants_all_contracts = _wants_all_contracts(question)

    if wants_all_contracts:
        contracts = _available_contracts()
    else:
        contracts = _detect_multiple_contracts(question)

    tool_plan: list[dict[str, Any]] = []

    if _is_top_or_ranked_question(question):
        limit = _detect_limit(question)
        direction = _detect_direction(question)

        for metric in metrics:
            for period_type in period_types:
                comparator = _comparator_for_period(comparators[0], period_type)

                tool_plan.append(
                    {
                        "tool_name": "top_variance",
                        "args": {
                            "metric": metric,
                            "period_type": period_type,
                            "comparator": comparator,
                            "category": category,
                            "direction": direction,
                            "limit": limit,
                        },
                    }
                )

        return _dedupe_tool_plan(tool_plan)

    # Specific finance questions:
    # - If user says all contracts/by contract/every contract, fan out to all contracts.
    # - If user mentions multiple contracts, fan out to those contracts.
    # - If no contract is mentioned, use category or total logic from tool layer.
    contracts_to_use: list[str | None] = contracts if contracts else [None]

    for contract in contracts_to_use:
        for metric in metrics:
            for period_type in period_types:
                for comparator in comparators:
                    mapped_comparator = _comparator_for_period(comparator, period_type)

                    tool_plan.append(
                        {
                            "tool_name": "actual_vs_comparator",
                            "args": {
                                "metric": metric,
                                "period_type": period_type,
                                "comparator": mapped_comparator,
                                "category": None if contract else category,
                                "contract": contract,
                            },
                        }
                    )

    return _dedupe_tool_plan(tool_plan)


def _extract_rows_from_tool_results(tool_results: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for raw_result in tool_results or []:
        result = _to_plain_dict(raw_result)

        if not isinstance(result, dict):
            continue

        if not result.get("success", False):
            continue

        data = _to_plain_dict(result.get("data") or {})

        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                rows.extend(data["data"])

            elif isinstance(data.get("rows"), list):
                rows.extend(data["rows"])

            elif isinstance(data.get("result"), list):
                rows.extend(data["result"])

            elif any(
                key in data
                for key in [
                    "actual",
                    "variance",
                    "contract",
                    "category",
                    "metric",
                    "period_type",
                ]
            ):
                rows.append(data)

        elif isinstance(data, list):
            rows.extend(data)

    return [row for row in rows if isinstance(row, dict)]


def _format_amount(value: Any) -> str:
    return f"{_as_float(value):,.1f}"


def _friendly_period(period_type: Any) -> str:
    text = str(period_type or "")
    return text.replace("_", " ").title()


def _friendly_metric(metric: Any) -> str:
    text = str(metric or "")

    if text.lower() == "profit":
        return "TP"

    return text.title()


def _friendly_comparator(row: dict[str, Any]) -> str:
    comparator_name = row.get("comparator_name")

    if comparator_name:
        return str(comparator_name)

    comparator = str(row.get("comparator") or "Comparator")
    return comparator.replace("_", " ").title()


def _row_label(row: dict[str, Any]) -> str:
    return str(
        row.get("contract")
        or row.get("category")
        or row.get("label")
        or "Finance item"
    )


def _build_answer_text(question: str, tool_results: list[Any]) -> str:
    rows = _extract_rows_from_tool_results(tool_results)

    if not rows:
        plain_results = _to_plain_dict(tool_results)
        failed = [
            result
            for result in plain_results or []
            if isinstance(result, dict) and not result.get("success", False)
        ]

        if failed:
            errors = [
                str(result.get("error"))
                for result in failed
                if result.get("error")
            ]

            error_text = "\n".join(f"- {error}" for error in errors[:5])

            return (
                "I could not calculate a finance answer for this question.\n\n"
                f"Question: {question}\n\n"
                f"{error_text}"
            )

        return (
            "I could not find matching finance rows for this question.\n\n"
            f"Question: {question}"
        )

    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        label = _row_label(row)

        if label not in grouped:
            grouped[label] = []

        grouped[label].append(row)

    lines: list[str] = []
    lines.append("Here is the detailed contract-wise finance view based on the approved calculation tools:")
    lines.append("")
    lines.append(f"Question: {question}")
    lines.append("")
    lines.append(f"Contracts analysed: {len(grouped)}")
    lines.append(f"Finance rows calculated: {len(rows)}")
    lines.append("")

    for contract_name, contract_rows in grouped.items():
        lines.append(f"{contract_name}")
        lines.append("-" * len(contract_name))

        for row in contract_rows:
            period = _friendly_period(row.get("period_type"))
            metric = _friendly_metric(row.get("metric"))
            comparator_name = _friendly_comparator(row)

            actual = _format_amount(row.get("actual"))
            comparator_value = _format_amount(row.get("comparator_value"))
            variance = _format_amount(row.get("variance"))

            variance_number = _as_float(row.get("variance"))

            if variance_number > 0:
                tone = "favourable"
            elif variance_number < 0:
                tone = "adverse"
            else:
                tone = "neutral"

            lines.append(
                f"- {period} {metric}: "
                f"Actual {actual} vs {comparator_name} {comparator_value}, "
                f"variance {variance} ({tone})."
            )

        lines.append("")

    return "\n".join(lines).strip()


def ask_deterministic_from_sqlite(question: str) -> dict[str, Any]:
    tool_plan = build_deterministic_tool_plan(question)

    if not tool_plan:
        return {
            "question": question,
            "mode": "deterministic",
            "used_fallback": False,
            "can_answer": False,
            "answer": (
                "I could not create a finance tool plan for this question. "
                "Please mention a metric such as revenue, TP/profit, or cash."
            ),
            "tool_plan": [],
            "tool_results": [],
            "reflection": "No deterministic tool plan was created.",
        }

    try:
        raw_tool_results = execute_finance_tool_plan(tool_plan)
        tool_results = _to_plain_dict(raw_tool_results)

    except Exception as exc:
        return {
            "question": question,
            "mode": "deterministic",
            "used_fallback": False,
            "can_answer": False,
            "answer": f"The deterministic finance planner failed while running tools: {exc}",
            "tool_plan": tool_plan,
            "tool_results": [],
            "reflection": "Tool execution failed.",
        }

    rows = _extract_rows_from_tool_results(tool_results)
    answer_text = _build_answer_text(question, tool_results)

    return {
        "question": question,
        "mode": "deterministic",
        "used_fallback": False,
        "can_answer": bool(rows),
        "answer": answer_text,
        "tool_plan": tool_plan,
        "tool_results": tool_results,
        "reflection": (
            f"Deterministic planner created {len(tool_plan)} tool call(s) "
            f"and returned {len(rows)} finance row(s)."
        ),
    }


def ask_deterministic(question: str) -> dict[str, Any]:
    return ask_deterministic_from_sqlite(question)


def plan_deterministic_from_sqlite(question: str) -> list[dict[str, Any]]:
    return build_deterministic_tool_plan(question)