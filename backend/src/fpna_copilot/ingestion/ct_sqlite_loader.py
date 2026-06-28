from __future__ import annotations

from pathlib import Path
from typing import Any

from fpna_copilot.column_rules import COLUMN_RULES, SHEET_NAME, UNIT
from fpna_copilot.ct_engine import CTNarrativeEngine, DEFAULT_EXCEL_PATH
from fpna_copilot.store.sqlite_store import SQLiteStore, store


def build_upload_id(period: str, source_name: str) -> str:
    """
    Build a stable upload id.

    Example:
    May 2026 + CFO_Summary_May.xlsx -> may_2026_cfo_summary_may
    """

    raw = f"{period}_{Path(source_name).stem}".lower()

    cleaned = "".join(
        char if char.isalnum() else "_"
        for char in raw
    )

    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")

    return cleaned.strip("_")


def ct_engine_to_fact_rows(
    engine: CTNarrativeEngine,
    *,
    upload_id: str,
    file_name: str,
    period: str = "May 2026",
    year: int = 2026,
    month: str = "May",
) -> list[dict[str, Any]]:
    """
    Convert the old wide CT engine dataframe into normalized fact_finance rows.

    Old CT engine shape:
    - one row per contract
    - many finance columns, e.g. in_month_revenue_actual

    New SQLite shape:
    - one row per contract + period_type + metric + scenario
    - easier future DB migration
    - easier multi-month comparison
    """

    rows: list[dict[str, Any]] = []

    detail_df = engine.df[engine.df["is_detail_row"]].copy()

    for _, source_row in detail_df.iterrows():
        category = source_row.get("category", "")
        contract = source_row.get("contract", "")
        excel_row = int(source_row.get("excel_row", 0))

        for period_type, metrics in COLUMN_RULES.items():
            for metric, fields in metrics.items():
                comment_value = source_row.get(f"{period_type}_{metric}_comment", "")

                for scenario, _excel_column in fields.items():
                    if scenario == "comment":
                        continue

                    value_column = f"{period_type}_{metric}_{scenario}"
                    value = float(source_row.get(value_column, 0.0) or 0.0)

                    rows.append(
                        {
                            "upload_id": upload_id,
                            "file_name": file_name,
                            "sheet_name": SHEET_NAME,
                            "period": period,
                            "year": year,
                            "month": month,
                            "period_type": period_type,
                            "entity_type": "contract",
                            "entity_name": contract,
                            "contract": contract,
                            "category": category,
                            "country": category,
                            "sector": None,
                            "metric": metric,
                            "scenario": scenario,
                            "value": value,
                            "currency": "GBP",
                            "unit": UNIT,
                            "comment": comment_value,
                            "excel_row": excel_row,
                        }
                    )

    return rows


def load_ct_narrative_to_sqlite(
    excel_path: str | Path = DEFAULT_EXCEL_PATH,
    *,
    db_store: SQLiteStore = store,
    period: str = "May 2026",
    year: int = 2026,
    month: str = "May",
    clear_existing: bool = True,
) -> dict[str, Any]:
    """
    Load CT-Narrative Excel data into SQLite fact_finance.

    This gives us persistent DB-style data while still preserving the old
    deterministic CT engine logic.
    """

    excel_path = Path(excel_path)
    upload_id = build_upload_id(period, excel_path.name)

    engine = CTNarrativeEngine(excel_path=excel_path)

    rows = ct_engine_to_fact_rows(
        engine,
        upload_id=upload_id,
        file_name=excel_path.name,
        period=period,
        year=year,
        month=month,
    )

    if clear_existing:
        db_store.clear_all()

    db_store.add_fact_rows(rows)

    return {
        "upload_id": upload_id,
        "file_name": excel_path.name,
        "sheet_name": SHEET_NAME,
        "period": period,
        "year": year,
        "month": month,
        "rows_inserted": len(rows),
        "detail_contract_rows": int(engine.df["is_detail_row"].sum()),
    }