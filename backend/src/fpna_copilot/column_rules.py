"""Strict CT-Narrative column rules.

These mappings intentionally use Excel column letters, not parsed workbook headers.
Only the CT-Narrative sheet is allowed.
"""

from __future__ import annotations

from typing import Final

SHEET_NAME: Final[str] = "CT-Narrative"
DATA_START_ROW: Final[int] = 6
UNIT: Final[str] = "£'000"

CATEGORY_COLUMN: Final[str] = "B"
CONTRACT_COLUMN: Final[str] = "C"

# IMPORTANT:
# These rules are copied from the user's strict requirement.
# Do not infer different meanings from workbook row headers.
COLUMN_RULES: Final[dict[str, dict[str, dict[str, str]]]] = {
    "in_month": {
        "revenue": {
            "actual": "E",
            "lbe": "F",
            "variance_lbe": "G",
            "business_plan": "H",
            "variance_bp": "I",
            "comment": "AO",
        },
        "profit": {
            "actual": "K",
            "lbe": "L",
            "variance_lbe": "M",
            "business_plan": "N",
            "variance_bp": "O",
            "comment": "AP",
        },
        "cash": {
            "actual": "Q",
            "lbe": "R",
            "variance_lbe": "S",
            "business_plan": "T",
            "variance_bp": "U",
            "comment": "AQ",
        },
    },
    "ytd": {
        "revenue": {
            "actual": "W",
            "budget": "X",
            "variance_budget": "Y",
            "actual_2025": "Z",
            "variance_actual_2025": "AA",
            "comment": "AO",
        },
        "profit": {
            "actual": "AC",
            "budget": "AD",
            "variance_budget": "AE",
            "actual_2025": "AF",
            "variance_actual_2025": "AG",
            "comment": "AP",
        },
        "cash": {
            "actual": "AI",
            "budget": "AJ",
            "variance_budget": "AK",
            "actual_2025": "AL",
            "variance_actual_2025": "AM",
            "comment": "AQ",
        },
    },
}

METRIC_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "revenue": (
        "revenue",
        "rev",
        "sales",
        "income",
        "turnover",
    ),
    "profit": (
        "profit",
        "trading profit",
        "tp",
        "uop",
        "underlying operating profit",
        "underline operating profit",
        "underlying operating prfit",
        "underline opertainfg profit",
        "underlying opertainfg profit",
        "operating profit",
    ),
    "cash": (
        "cash",
        "fcf",
        "free cash flow",
        "free cahs flow",
        "free cash",
    ),
}

PERIOD_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "in_month": (
        "in month",
        "in-month",
        "month",
        "monthly",
        "current month",
        "inmonth",
        "onmonth",
        "on month",
        "mtd",
        "month to date",
        "may",
    ),
    "ytd": (
        "ytd",
        "year to date",
        "year-to-date",
        "year till date",
    ),
}
