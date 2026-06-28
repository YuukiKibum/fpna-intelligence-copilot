from __future__ import annotations

from typing import Any

from fpna_copilot.models import FPNAAnswer


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    actual = _as_float(row.get("actual"))
    comparator_value = _as_float(
        row.get("comparator_value", row.get("lbe", row.get("budget", 0)))
    )
    variance = _as_float(row.get("variance"))

    metric = _as_text(row.get("metric"), "metric")
    period_type = _as_text(row.get("period_type"), "period")
    comparator = _as_text(row.get("comparator"), "")
    comparator_name = _as_text(
        row.get("comparator_name"),
        comparator.replace("_", " ").title() if comparator else "Comparator",
    )

    contract = _as_text(row.get("contract"), "")
    category = _as_text(row.get("category"), "")

    label_parts = []
    if contract:
        label_parts.append(contract)
    elif category:
        label_parts.append(category)

    if period_type:
        label_parts.append(period_type.replace("_", " ").title())

    if metric:
        label_parts.append(metric.title())

    label = " · ".join(label_parts) if label_parts else "Finance item"

    return {
        **row,
        "actual": actual,
        "comparator_value": comparator_value,
        "variance": variance,
        "metric": metric,
        "period_type": period_type,
        "comparator": comparator,
        "comparator_name": comparator_name,
        "contract": contract,
        "category": category,
        "label": label,
        "unit": row.get("unit") or "£'000",
        "comment": row.get("comment") or row.get("comments") or "",
    }


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

    return [_normalise_row(row) for row in rows if isinstance(row, dict)]


def _sort_by_abs_variance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: abs(_as_float(row.get("variance"))), reverse=True)


def _variance_tone(value: float) -> str:
    if value > 0:
        return "favourable"
    if value < 0:
        return "adverse"
    return "neutral"


def _make_executive_summary(
    question: str,
    rows: list[dict[str, Any]],
    answer_text: str,
    mode: str | None,
) -> dict[str, Any]:
    sorted_rows = _sort_by_abs_variance(rows)
    top_row = sorted_rows[0] if sorted_rows else {}

    favourable_count = sum(1 for row in rows if _as_float(row.get("variance")) > 0)
    adverse_count = sum(1 for row in rows if _as_float(row.get("variance")) < 0)

    top_variance = _as_float(top_row.get("variance"))
    top_label = _as_text(top_row.get("contract") or top_row.get("category"), "Key item")

    if top_variance > 0:
        headline = f"{top_label} is the main favourable movement at {top_variance:,.1f}."
    elif top_variance < 0:
        headline = f"{top_label} is the main adverse movement at {top_variance:,.1f}."
    else:
        headline = "The result is broadly neutral based on the available rows."

    return {
        "type": "executive_summary_card",
        "title": "Executive Summary",
        "props": {
            "question": question,
            "headline": headline,
            "mode": mode or "deterministic",
            "row_count": len(rows),
            "favourable_count": favourable_count,
            "adverse_count": adverse_count,
            "top_label": top_label,
            "top_variance": top_variance,
            "top_tone": _variance_tone(top_variance),
            "answer_text": answer_text,
        },
    }


def _make_kpi_strip(rows: list[dict[str, Any]], title: str = "KPI Snapshot") -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for row in rows:
        metric = _as_text(row.get("metric"), "metric").title()
        period = _as_text(row.get("period_type"), "").replace("_", " ").title()
        contract = _as_text(row.get("contract") or row.get("category"), "Finance item")

        variance = _as_float(row.get("variance"))

        items.append(
            {
                "label": f"{contract} · {metric}",
                "period": period,
                "actual": _as_float(row.get("actual")),
                "comparator_name": _as_text(row.get("comparator_name"), "Comparator"),
                "comparator_value": _as_float(row.get("comparator_value")),
                "variance": variance,
                "tone": _variance_tone(variance),
                "unit": row.get("unit") or "£'000",
            }
        )

    return {
        "type": "kpi_strip",
        "title": title,
        "props": {
            "items": items,
        },
    }


def _make_ranked_variance_chart(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_rows = _sort_by_abs_variance(rows)[:10]

    chart_rows = []
    for row in sorted_rows:
        label = _as_text(row.get("contract") or row.get("category") or row.get("label"))
        if len(label) > 38:
            label = label[:35] + "..."

        chart_rows.append(
            {
                "label": label,
                "full_label": row.get("label"),
                "variance": _as_float(row.get("variance")),
                "actual": _as_float(row.get("actual")),
                "comparator_value": _as_float(row.get("comparator_value")),
                "comparator_name": _as_text(row.get("comparator_name"), "Comparator"),
                "metric": _as_text(row.get("metric"), ""),
                "period_type": _as_text(row.get("period_type"), ""),
            }
        )

    return {
        "type": "ranked_variance_chart",
        "title": "Ranked Variance View",
        "props": {
            "rows": chart_rows,
            "unit": "£'000",
        },
    }


def _make_metric_comparison_cards(
    rows: list[dict[str, Any]],
    title: str = "Metric Comparison",
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []

    for row in rows:
        variance = _as_float(row.get("variance"))

        cards.append(
            {
                "title": row.get("label"),
                "contract": row.get("contract"),
                "category": row.get("category"),
                "metric": _as_text(row.get("metric"), "").title(),
                "period": _as_text(row.get("period_type"), "")
                .replace("_", " ")
                .title(),
                "actual": _as_float(row.get("actual")),
                "comparator_name": _as_text(row.get("comparator_name"), "Comparator"),
                "comparator_value": _as_float(row.get("comparator_value")),
                "variance": variance,
                "tone": _variance_tone(variance),
                "unit": row.get("unit") or "£'000",
                "comment": row.get("comment") or "",
            }
        )

    return {
        "type": "metric_comparison_card",
        "title": title,
        "props": {
            "cards": cards,
        },
    }


def _make_risk_opportunity_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_rows = _sort_by_abs_variance(rows)

    adverse = [row for row in sorted_rows if _as_float(row.get("variance")) < 0]
    favourable = [row for row in sorted_rows if _as_float(row.get("variance")) > 0]

    biggest_adverse = adverse[0] if adverse else None
    biggest_favourable = favourable[0] if favourable else None

    return {
        "type": "risk_opportunity_card",
        "title": "Risk & Opportunity",
        "props": {
            "biggest_adverse": biggest_adverse,
            "biggest_favourable": biggest_favourable,
            "adverse_count": len(adverse),
            "favourable_count": len(favourable),
            "unit": "£'000",
        },
    }


def _make_cfo_insight(answer_text: str) -> dict[str, Any]:
    return {
        "type": "cfo_insight",
        "title": "CFO Insight",
        "props": {
            "text": answer_text,
        },
    }


def _make_finance_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "table",
        "title": "Finance Detail",
        "props": {
            "rows": rows,
        },
    }


def _make_empty_state(question: str, answer_text: str) -> dict[str, Any]:
    return {
        "type": "empty_state",
        "title": "No Finance Rows Found",
        "props": {
            "question": question,
            "message": answer_text
            or "I could not find matching finance rows for this question.",
        },
    }


def _choose_dynamic_components(
    question: str,
    rows: list[dict[str, Any]],
    answer_text: str,
    mode: str | None,
) -> list[dict[str, Any]]:
    if not rows:
        return [_make_empty_state(question, answer_text)]

    lowered_question = question.lower()
    contract_groups = _group_rows_by_contract(rows)
    has_multiple_contracts = len(contract_groups) > 1

    components: list[dict[str, Any]] = []

    # 1. Executive summary first
    components.append(
        _make_executive_summary(
            question=question,
            rows=rows,
            answer_text=answer_text,
            mode=mode,
        )
    )

    # 2. CFO insight immediately after executive summary
    components.append(_make_cfo_insight(answer_text))

    is_top_or_ranked = any(
        phrase in lowered_question
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

    # 3. For multi-contract questions, create separate card sections per contract
    if has_multiple_contracts and not is_top_or_ranked:
        components.append(_make_kpi_strip(rows, title="All Contracts KPI Snapshot"))

        for contract_name, contract_rows in contract_groups:
            components.append(
                _make_metric_comparison_cards(
                    contract_rows,
                    title=f"{contract_name} · Metric Comparison",
                )
            )

    else:
        is_single_focus = len(rows) <= 10 and not is_top_or_ranked

        if is_single_focus:
            components.append(_make_kpi_strip(rows))
            components.append(_make_metric_comparison_cards(rows))
        else:
            components.append(_make_ranked_variance_chart(rows))

    # 4. Risk/opportunity and detail table
    components.append(_make_risk_opportunity_card(rows))
    components.append(_make_finance_table(rows))

    return components


def _followups(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return [
            "Show top 5 revenue variance in UAE",
            "Show Tamasuk in-month revenue against LBE",
        ]

    metrics = sorted({str(row.get("metric")) for row in rows if row.get("metric")})
    categories = sorted({str(row.get("category")) for row in rows if row.get("category")})
    contracts = sorted({str(row.get("contract")) for row in rows if row.get("contract")})

    followups = []

    if metrics:
        followups.append(f"Show the same view for {metrics[0]} YTD")

    if categories:
        followups.append(f"Show top 5 adverse variances in {categories[0]}")

    if contracts:
        followups.append(f"Explain revenue, profit, and cash for {contracts[0]}")

    followups.append("Show only adverse movements")

    return followups[:4]


def build_fpna_answer_from_service_result(service_result: dict[str, Any]) -> FPNAAnswer:
    question = _as_text(service_result.get("question"), "")
    answer_text = _as_text(service_result.get("answer"), "")
    mode = service_result.get("mode")
    used_fallback = bool(service_result.get("used_fallback", False))
    tool_plan = service_result.get("tool_plan") or []
    tool_results = service_result.get("tool_results") or []
    reflection = service_result.get("reflection")

    can_answer = bool(service_result.get("can_answer", True))

    rows = _extract_rows(tool_results)

    if not can_answer:
        components = [_make_empty_state(question, answer_text)]
        confidence = 0.3
    else:
        components = _choose_dynamic_components(
            question=question,
            rows=rows,
            answer_text=answer_text,
            mode=mode,
        )
        confidence = 0.9 if rows else 0.5

    assumptions = [
        "Values are shown in £'000 unless otherwise stated.",
        "Finance calculations are produced by approved backend tools, not by the UI renderer.",
        "The UI layout is selected dynamically based on the shape of the query result.",
    ]

    return FPNAAnswer(
        answer_text=answer_text,
        tool_results=tool_results,
        ui_spec={
            "layout": "dashboard",
            "components": components,
        },
        follow_up_questions=_followups(rows),
        assumptions=assumptions,
        confidence=confidence,
        mode=mode,
        used_fallback=used_fallback,
        tool_plan=tool_plan,
        reflection=reflection,
    )

def _group_rows_by_contract(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        group_name = _as_text(
            row.get("contract") or row.get("category") or "Finance item",
            "Finance item",
        )

        if group_name not in grouped:
            grouped[group_name] = []

        grouped[group_name].append(row)

    return list(grouped.items())