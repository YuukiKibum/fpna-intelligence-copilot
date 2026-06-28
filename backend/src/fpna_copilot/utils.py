from __future__ import annotations

from typing import Any
import math
import re

import pandas as pd
from openpyxl.utils import column_index_from_string


def excel_col_to_idx(col_letter: str) -> int:
    return column_index_from_string(col_letter) - 1


def clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, bool):
        return "" if value is False else "True"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # In this workbook, numeric 0 in text columns is used as a blank placeholder.
        if float(value) == 0:
            return ""
    text = str(value).strip()
    if text.lower() in {"0", "false", "nan", "none"}:
        return ""
    return text


def clean_number(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0.0

    if isinstance(value, bool):
        return 0.0

    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return 0.0
        return float(value)

    text = str(value).strip()
    if text in {"", "-", "—", "nan", "None", "N/A", "n/a"}:
        return 0.0

    text = (
        text.replace(",", "")
        .replace("£", "")
        .replace("AED", "")
        .replace("$", "")
        .strip()
    )

    # Finance negative format, e.g. (1,234.5)
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    try:
        return float(text)
    except ValueError:
        return 0.0


def norm(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_phrase(question: str, phrases: tuple[str, ...] | list[str]) -> bool:
    q = norm(question)
    return any(norm(phrase) in q for phrase in phrases)


def fmt_money(value: float) -> str:
    # Values are in £'000. Keep one decimal for CFO-style summaries.
    if abs(value) >= 1000:
        return f"{value:,.1f}"
    return f"{value:,.1f}"


def safe_snippet(text: str, max_len: int = 180) -> str:
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."
