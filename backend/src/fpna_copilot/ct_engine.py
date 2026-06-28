from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from .column_rules import (
    CATEGORY_COLUMN,
    COLUMN_RULES,
    CONTRACT_COLUMN,
    DATA_START_ROW,
    METRIC_ALIASES,
    PERIOD_ALIASES,
    SHEET_NAME,
    UNIT,
)
from .models import AgentAnswer, Comparator, Metric, MetricOrAll, Period, QuerySpec
from .utils import clean_number, clean_text, contains_phrase, excel_col_to_idx, fmt_money, norm, safe_snippet


DEFAULT_EXCEL_PATH = Path(__file__).resolve().parents[3] / "data" / "CFO_Summary_May.xlsx"


class CTNarrativeEngine:
    """Deterministic analysis engine for the CT-Narrative sheet.

    The LLM should never calculate finance numbers directly. This engine loads only
    CT-Narrative and reads only the fixed column letters defined in column_rules.py.
    """

    def __init__(self, excel_path: str | Path = DEFAULT_EXCEL_PATH):
        self.excel_path = Path(excel_path)
        self.df = self._load_ct_narrative()
        detail = self.df[self.df["is_detail_row"]].copy()
        self.categories = sorted(c for c in detail["category"].dropna().unique().tolist() if c)
        self.contracts = sorted(c for c in detail["contract"].dropna().unique().tolist() if c)

    def _load_ct_narrative(self) -> pd.DataFrame:
        if not self.excel_path.exists():
            raise FileNotFoundError(
                f"Excel file not found: {self.excel_path}. Put CFO_Summary_May.xlsx in the data folder."
            )

        # STRICT: only CT-Narrative, no other sheets.
        raw = pd.read_excel(
            self.excel_path,
            sheet_name=SHEET_NAME,
            header=None,
            skiprows=DATA_START_ROW - 1,
            engine="openpyxl",
        )

        data = pd.DataFrame()
        data["excel_row"] = range(DATA_START_ROW, DATA_START_ROW + len(raw))
        data["category"] = raw.iloc[:, excel_col_to_idx(CATEGORY_COLUMN)].map(clean_text)
        data["contract"] = raw.iloc[:, excel_col_to_idx(CONTRACT_COLUMN)].map(clean_text)

        for period, metrics in COLUMN_RULES.items():
            for metric, fields in metrics.items():
                for field, col_letter in fields.items():
                    col_name = f"{period}_{metric}_{field}"
                    series = raw.iloc[:, excel_col_to_idx(col_letter)]
                    data[col_name] = series.map(clean_text if field == "comment" else clean_number)

        # Keep only rows with a contract/name in Column C. Numeric 0/False placeholders are
        # converted to blank by clean_text and removed here.
        data = data[data["contract"] != ""].copy()

        # The uploaded CT-Narrative contains contract-level rows first, then repeated summary
        # blocks near the bottom. For contract-level questions and totals, we use the detail
        # section only to avoid double counting. The first SME/SME row marks the summary area
        # in this workbook format. If it ever is not present, all non-total rows are treated
        # as detail rows.
        summary_markers = data[
            (data["category"].str.lower() == "sme")
            & (data["contract"].str.lower() == "sme")
        ]
        summary_start_row = int(summary_markers["excel_row"].min()) if not summary_markers.empty else 10**9

        total_like = (
            data["category"].str.lower().str.contains("total", na=False)
            | data["contract"].str.lower().str.contains("total", na=False)
            | (data["category"] == "")
        )
        data["is_total_or_summary_row"] = total_like | (data["excel_row"] >= summary_start_row)
        data["is_detail_row"] = ~data["is_total_or_summary_row"]

        data.reset_index(drop=True, inplace=True)
        return data

    # ---------------------------
    # Query interpretation
    # ---------------------------
    def detect_periods(self, question: str) -> list[Period]:
        """Return all periods explicitly requested by the user.

        CFO users often type short prompts such as:
        - "Tamasuk in month and YTD revenue TP cash"
        - "both YTD and onmonth cash"

        If no period is mentioned, the strict business rule is to default to
        in-month only. Words such as budget must never force YTD.
        """
        q = question.lower()
        periods: list[Period] = []

        both_signal = any(term in q for term in ["both", "all periods", "both periods", "ytd and", "and ytd"])
        has_ytd = contains_phrase(q, PERIOD_ALIASES["ytd"])
        has_in_month = contains_phrase(q, PERIOD_ALIASES["in_month"])

        if has_in_month or (both_signal and has_ytd):
            periods.append("in_month")
        if has_ytd:
            periods.append("ytd")

        if not periods:
            periods.append("in_month")

        # Keep stable display order: in-month first, then YTD.
        ordered: list[Period] = []
        for period in ["in_month", "ytd"]:
            if period in periods and period not in ordered:
                ordered.append(period)  # type: ignore[arg-type]
        return ordered

    def detect_period(self, question: str) -> Period:
        return self.detect_periods(question)[0]

    def detect_metrics(self, question: str) -> list[Metric]:
        """Return every metric explicitly requested in the question.

        Important for short CFO prompts like:
        - "Tamasuk actual revenue TP and cash"
        - "revenue and cash for UAE"

        The old version returned the first detected metric only, so TP/cash could be
        dropped when revenue appeared first.
        """
        found: list[Metric] = []
        for metric, aliases in METRIC_ALIASES.items():
            if contains_phrase(question, aliases):
                found.append(metric)  # type: ignore[arg-type]
        return found

    def detect_metric(self, question: str) -> MetricOrAll:
        found = self.detect_metrics(question)
        if len(found) == 1:
            return found[0]
        # None or multiple both use "all" in the legacy field. The exact multi-metric
        # list is stored separately in QuerySpec.requested_metrics.
        return "all"

    def detect_comparator(self, question: str, period: Period) -> Comparator | None:
        q = question.lower()
        if any(term in q for term in ["lbe", "forecast"]):
            return "lbe" if period == "in_month" else "budget"
        if any(term in q for term in ["business plan", "bp"]):
            return "business_plan" if period == "in_month" else "budget"
        if "budget" in q:
            return "budget" if period == "ytd" else "business_plan"
        if "2025" in q or "last year" in q or "prior year" in q or "py" in q:
            return "actual_2025" if period == "ytd" else None
        # Default comparator for variance questions.
        return "lbe" if period == "in_month" else "budget"

    def detect_top_n(self, question: str, default: int = 10) -> int:
        q = question.lower()
        match = re.search(r"(?:top|bottom|highest|largest|lowest|worst|best)\s+(\d+)", q)
        if match:
            return max(1, min(100, int(match.group(1))))
        return default

    def detect_variance_direction(self, question: str) -> str:
        q = question.lower()
        if any(term in q for term in ["adverse", "negative", "unfavourable", "unfavorable", "worse", "worst", "downside"]):
            return "adverse"
        if any(term in q for term in ["favourable", "favorable", "positive", "better", "upside", "best"]):
            return "favourable"
        return "absolute"

    def detect_question_type(self, question: str) -> str:
        q = question.lower().strip()
        nq = norm(q)

        if not q:
            return "unknown"
        if any(term in nq for term in ["overview", "brief", "summarize data", "summarise data", "what data", "what can you answer", "columns"]):
            return "overview"
        if any(term in nq for term in ["find contract", "search contract", "lookup contract", "contract details", "details for", "show contract"]):
            return "contract_details"
        if any(term in nq for term in ["list contracts", "show contracts", "which contracts"]):
            return "list_contracts"
        if any(term in nq for term in ["comment", "comments", "commentary", "why", "explain variance", "reason"]):
            return "comments"
        if any(term in nq for term in ["actual vs", "actual versus", "compare", "comparison", "variance vs"]):
            return "actual_vs_comparator"
        if any(term in nq for term in ["by country", "by category", "category breakdown", "country breakdown", "breakdown"]):
            return "category_breakdown"
        if any(term in nq for term in ["total", "sum", "overall", "aggregate"]):
            return "total"
        if any(term in nq for term in ["variance", "varaince", "gap", "delta", "movement", "deviation"]):
            return "ranking_variance"
        if any(term in nq for term in ["lowest", "bottom", "smallest"]):
            return "lowest_actual"
        if any(term in nq for term in ["highest", "largest", "top", "biggest"]):
            return "ranking_actual"
        if any(term in nq for term in ["search", "find", "lookup"]):
            return "entity_search"
        return "unknown"

    def interpret(self, question: str) -> QuerySpec:
        requested_periods = self.detect_periods(question)
        period = requested_periods[0]
        requested_metrics = self.detect_metrics(question)
        metric = requested_metrics[0] if len(requested_metrics) == 1 else "all"
        comparator = self.detect_comparator(question, period)
        qtype = self.detect_question_type(question)
        top_n = 1 if any(term in question.lower() for term in ["highest", "largest", "lowest", "smallest", "biggest"]) else self.detect_top_n(question)
        direction = self.detect_variance_direction(question)

        spec = QuerySpec(
            question=question,
            question_type=qtype,  # type: ignore[arg-type]
            metric=metric,
            requested_metrics=requested_metrics or None,
            period=period,
            requested_periods=requested_periods,
            comparator=comparator,
            variance_direction=direction,  # type: ignore[arg-type]
            top_n=top_n,
            group_by="category" if any(term in question.lower() for term in ["by country", "by category", "country breakdown", "category breakdown", "breakdown"]) else None,
        )

        category_match, contract_match = self._detect_scope(question)
        spec.category_query = category_match
        spec.contract_query = contract_match
        spec.scope_text = category_match or contract_match

        # Allow natural short CFO lookups such as:
        # "YTD Khadamat Cash", "in month ADAC CX revenue", "Khadamat", "UAE",
        # "cash", "profit budget", or "YTD".
        # If the prompt contains enough CT-Narrative signal but no action word,
        # answer safely instead of saying unknown. Category scopes are treated as
        # totals; contract scopes are treated as contract details. If no metric is
        # mentioned, all three metrics are returned for the default/explicit period.
        explicit_period = contains_phrase(question.lower(), PERIOD_ALIASES["ytd"]) or contains_phrase(question.lower(), PERIOD_ALIASES["in_month"])
        comparator_signal = any(term in question.lower() for term in ["budget", "business plan", "bp", "lbe", "forecast", "2025", "last year", "prior year", "py"])
        has_ct_signal = spec.scope_text or spec.metric != "all" or explicit_period or comparator_signal
        if spec.question_type == "unknown" and has_ct_signal:
            spec.question_type = "total" if spec.category_query or not spec.contract_query else "contract_details"

        return spec

    def _entity_query_text(self, question: str) -> str:
        """Remove finance words and keep the likely Column C entity phrase.

        CFO users often type compact prompts like:
        "dubai airport customer service revenue tp and cash".
        The entity is "dubai airport customer service"; metric words must not make
        contract matching broad.
        """
        q = norm(question)

        # Remove longer aliases first so phrases like "free cash flow" and
        # "year to date" disappear cleanly.
        phrases: list[str] = []
        for aliases in METRIC_ALIASES.values():
            phrases.extend(aliases)
        for aliases in PERIOD_ALIASES.values():
            phrases.extend(aliases)
        phrases.extend([
            "actual vs budget", "actual versus budget", "actual vs business plan",
            "actual versus business plan", "variance vs", "business plan",
            "contract details", "show contract", "find contract", "search contract",
            "list contracts", "which contracts", "search", "find", "lookup",
            "by country", "by category", "category breakdown", "country breakdown",
        ])
        for phrase in sorted({norm(p) for p in phrases if p}, key=len, reverse=True):
            q = re.sub(rf"\b{re.escape(phrase)}\b", " ", q)

        stop_words = {
            "actual", "lbe", "forecast", "budget", "variance", "varaince",
            "gap", "delta", "movement", "deviation", "comment", "comments",
            "commentary", "why", "explain", "reason", "total", "sum",
            "overall", "aggregate", "top", "bottom", "highest", "largest",
            "lowest", "smallest", "biggest", "best", "worst", "positive",
            "negative", "favourable", "favorable", "adverse", "unfavourable",
            "unfavorable", "contract", "contracts", "customer", "customers",
            # Keep customer/customers? No: contract names can contain them, so do NOT
            # remove those. They are intentionally removed from this set below.
            "for", "of", "in", "and", "or", "the", "a", "an", "vs",
            "versus", "with", "to", "from", "level", "details", "detail",
            "row", "rows", "number", "numbers", "value", "values", "all",
            "search", "find", "lookup", "both", "period", "periods", "metric", "metrics", "k", "000",
        }
        # Contract names in the workbook include "customer"/"customers", so keep them.
        stop_words.discard("customer")
        stop_words.discard("customers")

        words = [w for w in q.split() if w not in stop_words and not w.isdigit()]
        return norm(" ".join(words))

    def _best_contract_match(self, query: str) -> tuple[str | None, int]:
        """Return a single best Column C contract match for a user entity phrase.

        Matching order is deliberately precise:
        1. Exact normalized match
        2. Unique contains match
        3. Fuzzy match for plural/typo variations

        This prevents "dubai airport customer service" from returning every
        contract containing only the word "Dubai".
        """
        q = norm(query)
        if not q:
            return None, 0

        choices = {norm(c): c for c in self.contracts if c}

        # Exact full-contract match.
        if q in choices:
            return choices[q], 100

        # If the user phrase is contained in exactly one contract, use that one.
        contains_matches = [(c_norm, c) for c_norm, c in choices.items() if q in c_norm]
        if len(contains_matches) == 1:
            return contains_matches[0][1], 98

        # If a contract is contained in the user question, use the longest match.
        contained_contracts = [(c_norm, c) for c_norm, c in choices.items() if c_norm and c_norm in q]
        if contained_contracts:
            contained_contracts.sort(key=lambda item: len(item[0]), reverse=True)
            return contained_contracts[0][1], 97

        # Token-subset match for abbreviated contract phrases.
        # Example: "dubai customer service" should match
        # "DUBAI AIRPORTS CUSTOMER SERVICES" because all meaningful user tokens
        # are present after singular/plural normalization, while still avoiding
        # broad matches like "dubai airport" when several contracts match.
        def token_stem(token: str) -> str:
            token = token.strip()
            if len(token) > 3 and token.endswith("ies"):
                return token[:-3] + "y"
            if len(token) > 3 and token.endswith("s"):
                return token[:-1]
            return token

        query_tokens = {token_stem(t) for t in q.split() if len(t) > 2}
        if len(query_tokens) >= 2:
            subset_matches: list[tuple[str, str]] = []
            for c_norm, c in choices.items():
                contract_tokens = {token_stem(t) for t in c_norm.split() if len(t) > 2}
                if query_tokens.issubset(contract_tokens):
                    subset_matches.append((c_norm, c))
            if len(subset_matches) == 1:
                return subset_matches[0][1], 96

        # Fuzzy fallback for plural/typo variants, e.g.
        # "dubai airport customer service" -> "DUBAI AIRPORTS CUSTOMER SERVICES".
        if len(q.split()) >= 2:
            matches = process.extract(q, choices.keys(), scorer=fuzz.WRatio, limit=3)
            if matches:
                best_text, best_score, *_ = matches[0]
                second_score = matches[1][1] if len(matches) > 1 else 0
                # Require a strong score and enough gap from second place. This keeps
                # broad prompts like "dubai revenue" from selecting an arbitrary Dubai
                # contract.
                if best_score >= 86 and (best_score - second_score >= 5 or best_score >= 94):
                    return choices[best_text], int(best_score)

            # token_set_ratio is useful when the user omits small words or uses singular/plural.
            matches = process.extract(q, choices.keys(), scorer=fuzz.token_set_ratio, limit=3)
            if matches:
                best_text, best_score, *_ = matches[0]
                second_score = matches[1][1] if len(matches) > 1 else 0
                if best_score >= 88 and (best_score - second_score >= 5 or best_score >= 96):
                    return choices[best_text], int(best_score)

        return None, 0

    def _detect_scope(self, question: str) -> tuple[str | None, str | None]:
        """Detect scope from Column B and Column C without over-broad matches.

        Rules:
        - True country/category prompts such as "UAE" or "KSA" use Column B.
        - Specific contract-like phrases use Column C, even if they contain a place
          word such as Dubai.
        - SME level variance follows the user's rule and is not filtered to category
          SME; it is treated as the SME contract/detail scope from Column C logic.
        """
        q_norm = norm(question)
        entity_q = self._entity_query_text(question)

        if "sme" in q_norm:
            return None, None

        # 1. First check explicit Column B categories/countries. Use exact word
        # boundaries so "uae contracts" scopes to UAE, but "dubai airport..." does
        # not become a broad Dubai filter.
        for cat in self.categories:
            cat_norm = norm(cat)
            if cat_norm and re.search(rf"\b{re.escape(cat_norm)}\b", q_norm):
                return cat, None

        category_aliases = {
            "uae": ("uae",),
            "ksa": ("ksa", "saudi", "saudi arabia"),
            "qatar": ("qatar",),
            "oman": ("oman",),
            "bahrain": ("bahrain",),
            "kuwait": ("kuwait",),
        }
        for category_key, aliases in category_aliases.items():
            if any(re.search(rf"\b{re.escape(norm(alias))}\b", q_norm) for alias in aliases):
                for cat in self.categories:
                    if category_key in norm(cat):
                        return cat, None

        # 2. Then try precise Column C contract matching using the cleaned entity
        # phrase. This avoids returning all contracts starting with a shared word.
        contract, score = self._best_contract_match(entity_q)
        if contract:
            return None, contract

        # 3. Last fallback: try the full question, but only for strong multi-word
        # matches.
        contract, score = self._best_contract_match(q_norm)
        if contract and len(q_norm.split()) >= 2 and score >= 88:
            return None, contract

        return None, None

    # ---------------------------
    # Column helpers
    # ---------------------------
    def metric_list(self, metric_or_spec: MetricOrAll | QuerySpec) -> list[Metric]:
        if isinstance(metric_or_spec, QuerySpec):
            if metric_or_spec.requested_metrics:
                return metric_or_spec.requested_metrics
            metric = metric_or_spec.metric
        else:
            metric = metric_or_spec

        if metric == "all":
            return ["revenue", "profit", "cash"]
        return [metric]

    def period_list(self, spec: QuerySpec) -> list[Period]:
        return spec.requested_periods or [spec.period]

    def comparator_for_period(self, spec: QuerySpec, period: Period) -> Comparator | None:
        # Comparator meanings differ by period: in-month "budget" maps to Business
        # Plan, while YTD budget maps to Budget. Re-detect it per period so mixed
        # period questions use the correct strict columns for each section.
        return self.detect_comparator(spec.question, period)

    def actual_col(self, period: Period, metric: Metric) -> str:
        return f"{period}_{metric}_actual"

    def comment_col(self, period: Period, metric: Metric) -> str:
        return f"{period}_{metric}_comment"

    def variance_col_for(self, period: Period, metric: Metric, comparator: Comparator | None) -> tuple[str | None, str]:
        if period == "in_month":
            if comparator in [None, "lbe"]:
                return f"{period}_{metric}_variance_lbe", "LBE"
            if comparator == "business_plan":
                return f"{period}_{metric}_variance_bp", "Business Plan"
            # Budget and actual_2025 are not defined for in-month in the user's strict rules.
            return None, str(comparator)
        if period == "ytd":
            if comparator in [None, "budget", "lbe", "business_plan"]:
                return f"{period}_{metric}_variance_budget", "Budget"
            if comparator == "actual_2025":
                return f"{period}_{metric}_variance_actual_2025", "Actual 2025"
        return None, str(comparator)

    def compare_col_for(self, period: Period, metric: Metric, comparator: Comparator | None) -> tuple[str | None, str]:
        if period == "in_month":
            if comparator in [None, "lbe"]:
                return f"{period}_{metric}_lbe", "LBE"
            if comparator == "business_plan":
                return f"{period}_{metric}_business_plan", "Business Plan"
            return None, str(comparator)
        if period == "ytd":
            if comparator in [None, "budget", "lbe", "business_plan"]:
                return f"{period}_{metric}_budget", "Budget"
            if comparator == "actual_2025":
                return f"{period}_{metric}_actual_2025", "Actual 2025"
        return None, str(comparator)

    def columns_used_for(self, period: Period, metric: Metric) -> dict[str, str]:
        return COLUMN_RULES[period][metric].copy()

    # ---------------------------
    # Scoping
    # ---------------------------
    def apply_scope(self, spec: QuerySpec, *, detail_only: bool = True) -> pd.DataFrame:
        df = self.df[self.df["is_detail_row"]].copy() if detail_only else self.df.copy()
        if spec.category_query:
            return df[df["category"].str.lower() == spec.category_query.lower()].copy()
        if spec.contract_query:
            needle = norm(spec.contract_query)
            scoped = df[df["contract"].map(lambda x: needle in norm(x))].copy()
            if not scoped.empty:
                return scoped
        return df

    # ---------------------------
    # Public answer method
    # ---------------------------
    def answer_question(self, question: str) -> str:
        try:
            spec = self.interpret(question)

            handlers = {
                "overview": self._overview,
                "entity_search": self._entity_search,
                "contract_details": self._contract_details,
                "list_contracts": self._list_contracts,
                "ranking_variance": self._ranking_variance,
                "ranking_actual": self._ranking_actual,
                "lowest_actual": self._lowest_actual,
                "total": self._total,
                "actual_vs_comparator": self._actual_vs_comparator,
                "category_breakdown": self._category_breakdown,
                "comments": self._comments,
            }

            handler = handlers.get(spec.question_type)
            if handler is None:
                return self._unknown(
                    spec,
                    "The question could not be safely classified into a CT-Narrative calculation or lookup pattern.",
                ).model_dump_json(indent=2)

            if len(self.period_list(spec)) > 1 and spec.question_type not in {"overview", "entity_search", "list_contracts"}:
                return self._multi_period_answer(spec, handler).model_dump_json(indent=2)

            return handler(spec).model_dump_json(indent=2)
        except Exception as exc:
            safe = AgentAnswer(
                can_answer=False,
                answer="I don't know based on the CT-Narrative sheet.",
                question_spec=None,
                reflection=f"The engine hit an error and refused to guess: {type(exc).__name__}: {exc}",
                confidence="low",
            )
            return safe.model_dump_json(indent=2)

    def _multi_period_answer(self, spec: QuerySpec, handler) -> AgentAnswer:
        """Run the selected calculation once per requested period and combine output.

        This keeps all existing handlers deterministic while supporting CFO prompts like
        "Tamasuk in month and YTD revenue TP cash". Each section re-detects the
        comparator for that period so in-month uses LBE/Business Plan columns and
        YTD uses Budget/Actual 2025 columns.
        """
        answers: list[AgentAnswer] = []
        combined_columns: dict[str, Any] = {}
        combined_data: list[dict[str, Any]] = []
        total_rows_used = 0

        for period in self.period_list(spec):
            sub_spec = spec.model_copy(deep=True)
            sub_spec.period = period
            sub_spec.requested_periods = [period]
            sub_spec.comparator = self.comparator_for_period(spec, period)
            answer = handler(sub_spec)
            answers.append(answer)
            combined_columns[period] = answer.columns_used
            combined_data.extend(answer.data or [])
            total_rows_used += answer.rows_used

        successful = [a for a in answers if a.can_answer]
        if not successful:
            return self._unknown(spec, "; ".join(a.reflection for a in answers) or "No requested period could be answered safely.")

        answer_text = "\n\n".join(a.answer for a in successful)
        reflection = (
            "Handled a multi-period CT-Narrative question. "
            "Each requested period was calculated separately using only its fixed mapped columns: "
            + ", ".join(self.period_list(spec))
            + ". "
            + " | ".join(a.reflection for a in successful)
        )

        return AgentAnswer(
            can_answer=True,
            answer=answer_text,
            question_spec=spec,
            columns_used=combined_columns,
            reflection=reflection,
            confidence="high" if all(a.confidence == "high" for a in successful) else "medium",
            rows_used=total_rows_used,
            data=combined_data,
        )

    # ---------------------------
    # Handlers
    # ---------------------------
    def _overview(self, spec: QuerySpec) -> AgentAnswer:
        answer = (
            f"CT-Narrative contains {int(self.df['is_detail_row'].sum()):,} detail contract rows and {len(self.df):,} loaded CT-Narrative rows. "
            "I can answer finance questions for revenue, profit/TP/UOP, and cash/FCF across in-month and YTD views. "
            "Supported analysis includes top/bottom variances, highest actuals, totals, actual vs LBE/Budget/Business Plan, "
            "category breakdowns, contract lookups, and variance comments."
        )
        return AgentAnswer(
            can_answer=True,
            answer=answer,
            question_spec=spec,
            columns_used={
                "category": CATEGORY_COLUMN,
                "contract": CONTRACT_COLUMN,
                "strict_metric_rules": COLUMN_RULES,
            },
            reflection="Used only CT-Narrative metadata and the fixed column map. No finance numbers were inferred by the LLM.",
            confidence="high",
            rows_used=int(self.df["is_detail_row"].sum()),
        )

    def _entity_search(self, spec: QuerySpec) -> AgentAnswer:
        query = spec.scope_text or spec.question
        qn = norm(query)
        hits = []
        for _, row in self.df[self.df["is_detail_row"]].iterrows():
            if qn in norm(row["contract"]) or qn in norm(row["category"]):
                hits.append({"category": row["category"], "contract": row["contract"], "excel_row": int(row["excel_row"])})
        if not hits:
            # Fuzzy contract search.
            choices = {c: c for c in self.contracts}
            fuzzy = process.extract(query, choices.keys(), scorer=fuzz.partial_ratio, limit=10)
            hits = [
                {"category": self.df.loc[(self.df["contract"] == item[0]) & (self.df["is_detail_row"]), "category"].iloc[0], "contract": item[0], "match_score": item[1]}
                for item in fuzzy
                if item[1] >= 70
            ]
        if not hits:
            return self._unknown(spec, "No matching category or contract was found in Column B or Column C.")
        lines = ["Matching CT-Narrative entities:"] + [
            f"- {h['contract']} | Category: {h['category']}" + (f" | Row: {h.get('excel_row')}" if h.get("excel_row") else "")
            for h in hits[:20]
        ]
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used={"category": CATEGORY_COLUMN, "contract": CONTRACT_COLUMN},
            reflection="Searched only Column B category and Column C contract names in CT-Narrative.",
            confidence="medium",
            rows_used=len(hits),
            data=hits[:20],
        )

    def _contract_details(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty or len(df) == int(self.df["is_detail_row"].sum()):
            # Try using the question as a fuzzy contract query.
            choices = {c: c for c in self.contracts}
            match = process.extractOne(spec.question, choices.keys(), scorer=fuzz.partial_ratio)
            if match and match[1] >= 70:
                spec.contract_query = match[0]
                df = self.apply_scope(spec)
        if df.empty or len(df) == int(self.df["is_detail_row"].sum()):
            return self._unknown(spec, "No specific contract could be identified from Column C.")

        metrics = self.metric_list(spec)
        rows: list[dict[str, Any]] = []
        lines = [f"Contract details for {len(df):,} matching row(s):"]
        for _, r in df.head(20).iterrows():
            lines.append(f"\n- Contract: {r['contract']} | Category: {r['category']}")
            row_dict: dict[str, Any] = {"category": r["category"], "contract": r["contract"], "excel_row": int(r["excel_row"])}
            for metric in metrics:
                actual = r[self.actual_col(spec.period, metric)]
                var_col, comparator = self.variance_col_for(spec.period, metric, spec.comparator)
                compare_col, compare_name = self.compare_col_for(spec.period, metric, spec.comparator)
                comment = r[self.comment_col(spec.period, metric)]
                if var_col and compare_col:
                    lines.append(
                        f"  - {spec.period.replace('_', ' ').title()} {metric.title()}: "
                        f"Actual {fmt_money(actual)} vs {compare_name} {fmt_money(r[compare_col])}; "
                        f"Variance {fmt_money(r[var_col])}; Comment: {safe_snippet(comment) or 'No comment'}"
                    )
                    row_dict[f"{metric}_actual"] = actual
                    row_dict[f"{metric}_{compare_name.lower().replace(' ', '_')}"] = r[compare_col]
                    row_dict[f"{metric}_variance"] = r[var_col]
                    row_dict[f"{metric}_comment"] = comment
            rows.append(row_dict)
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used={metric: self.columns_used_for(spec.period, metric) for metric in metrics},
            reflection=f"Used only CT-Narrative Column C for contract matching and fixed {spec.period} metric columns.",
            confidence="high" if len(df) == 1 else "medium",
            rows_used=len(df),
            data=rows,
        )

    def _list_contracts(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching contracts were found for the requested category/scope.")
        lines = [f"Found {len(df):,} CT-Narrative contract row(s):"]
        for _, r in df.head(50).iterrows():
            lines.append(f"- {r['contract']} | Category: {r['category']}")
        if len(df) > 50:
            lines.append(f"...showing first 50 of {len(df):,} rows.")
        data = df[["category", "contract", "excel_row"]].head(50).to_dict("records")
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used={"category": CATEGORY_COLUMN, "contract": CONTRACT_COLUMN},
            reflection="Listed contracts using Column C and categories using Column B from CT-Narrative only.",
            confidence="high",
            rows_used=len(df),
            data=data,
        )

    def _ranking_variance(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")

        q = spec.question.lower()
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}

        for metric in self.metric_list(spec):
            actual_col = self.actual_col(spec.period, metric)
            var_col, comparator = self.variance_col_for(spec.period, metric, spec.comparator)
            compare_col, compare_name = self.compare_col_for(spec.period, metric, spec.comparator)

            if not var_col or not compare_col:
                return self._unknown(spec, f"The requested comparator is not supported for {spec.period} {metric} under the strict column rules.")

            comment_col = self.comment_col(spec.period, metric)
            columns_used[metric] = self.columns_used_for(spec.period, metric)

            # Ranking answers should still show the underlying values when the user asks
            # for actual/LBE/budget, e.g. "top 3 positive in month cash variance, actual,
            # LBE and budget". For in-month, casual "budget" maps to Business Plan
            # because strict columns define Business Plan, not Budget, for in-month.
            extra_cols: dict[str, str] = {}
            if spec.period == "in_month":
                if "lbe" in q or compare_name == "LBE":
                    extra_cols["lbe"] = f"{spec.period}_{metric}_lbe"
                if any(term in q for term in ["budget", "business plan", "bp"]) or compare_name == "Business Plan":
                    extra_cols["business_plan"] = f"{spec.period}_{metric}_business_plan"
            else:
                if "budget" in q or compare_name == "Budget":
                    extra_cols["budget"] = f"{spec.period}_{metric}_budget"
                if any(term in q for term in ["2025", "last year", "prior year", "py"]):
                    extra_cols["actual_2025"] = f"{spec.period}_{metric}_actual_2025"

            needed_cols = ["category", "contract", "excel_row", actual_col, compare_col, var_col, comment_col] + list(extra_cols.values())
            temp = df[list(dict.fromkeys(needed_cols))].copy()
            temp["metric"] = metric
            temp["actual"] = temp[actual_col]
            temp["comparator"] = comparator
            temp["comparator_name"] = compare_name
            temp["comparator_value"] = temp[compare_col]
            temp["variance"] = temp[var_col]
            temp["comment"] = temp[comment_col]
            for label, col in extra_cols.items():
                temp[label] = temp[col]

            selected_cols = [
                "category",
                "contract",
                "excel_row",
                "metric",
                "actual",
                "comparator",
                "comparator_name",
                "comparator_value",
                "variance",
                "comment",
            ] + list(extra_cols.keys())
            rows.extend(temp[selected_cols].to_dict("records"))

        result = pd.DataFrame(rows)
        if spec.variance_direction == "adverse":
            result = result.sort_values("variance", ascending=True)
        elif spec.variance_direction == "favourable":
            result = result.sort_values("variance", ascending=False)
        else:
            result = result.assign(abs_variance=result["variance"].abs()).sort_values("abs_variance", ascending=False)
        result = result.head(spec.top_n)

        period_label = spec.period.replace("_", " ")
        scope_label = f" for {spec.scope_text}" if spec.scope_text else ""
        metric_label = ", ".join(self.metric_list(spec)) if spec.requested_metrics else ("all metrics" if spec.metric == "all" else str(spec.metric))
        lines = [f"Top {len(result)} {period_label} {metric_label} variance item(s){scope_label} ({UNIT}):"]
        for _, r in result.iterrows():
            value_parts = [f"Actual: {fmt_money(float(r['actual']))}"]
            if "lbe" in result.columns and pd.notna(r.get("lbe")):
                value_parts.append(f"LBE: {fmt_money(float(r['lbe']))}")
            if "business_plan" in result.columns and pd.notna(r.get("business_plan")):
                value_parts.append(f"Business Plan: {fmt_money(float(r['business_plan']))}")
            if "budget" in result.columns and pd.notna(r.get("budget")):
                value_parts.append(f"Budget: {fmt_money(float(r['budget']))}")
            if "actual_2025" in result.columns and pd.notna(r.get("actual_2025")):
                value_parts.append(f"Actual 2025: {fmt_money(float(r['actual_2025']))}")

            # Ensure the selected comparator value is visible even when it was not explicitly
            # requested as an extra column.
            comp_name = str(r["comparator_name"])
            if not any(part.startswith(f"{comp_name}:") for part in value_parts):
                value_parts.append(f"{comp_name}: {fmt_money(float(r['comparator_value']))}")

            lines.append(
                f"- {r['contract']} | Category: {r['category']} | Metric: {str(r['metric']).title()} | "
                + " | ".join(value_parts)
                + f" | Variance vs {r['comparator']}: {fmt_money(float(r['variance']))} | "
                + f"Comment: {safe_snippet(r['comment']) or 'No comment'}"
            )

        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection=(
                f"Classified as a variance ranking. Used only CT-Narrative, Column B/Column C for scope, "
                f"and fixed {spec.period} variance columns. Ranking direction: {spec.variance_direction}."
            ),
            confidence="high",
            rows_used=len(df),
            data=result.drop(columns=["abs_variance"], errors="ignore").to_dict("records"),
        )


    def _ranking_actual(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}
        for metric in self.metric_list(spec):
            actual_col = self.actual_col(spec.period, metric)
            comment_col = self.comment_col(spec.period, metric)
            columns_used[metric] = self.columns_used_for(spec.period, metric)
            temp = df[["category", "contract", "excel_row", actual_col, comment_col]].copy()
            temp["metric"] = metric
            temp["actual"] = temp[actual_col]
            temp["comment"] = temp[comment_col]
            rows.extend(temp[["category", "contract", "excel_row", "metric", "actual", "comment"]].to_dict("records"))
        result = pd.DataFrame(rows).sort_values("actual", ascending=False).head(spec.top_n)
        lines = [f"Top {len(result)} {spec.period.replace('_', ' ')} actual item(s) ({UNIT}):"]
        for _, r in result.iterrows():
            lines.append(
                f"- {r['contract']} | Category: {r['category']} | Metric: {str(r['metric']).title()} | "
                f"Actual: {fmt_money(float(r['actual']))} | Comment: {safe_snippet(r['comment']) or 'No comment'}"
            )
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection=f"Classified as highest/top actual ranking and used fixed {spec.period} actual columns only.",
            confidence="high",
            rows_used=len(df),
            data=result.to_dict("records"),
        )

    def _lowest_actual(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}
        for metric in self.metric_list(spec):
            actual_col = self.actual_col(spec.period, metric)
            comment_col = self.comment_col(spec.period, metric)
            columns_used[metric] = self.columns_used_for(spec.period, metric)
            temp = df[["category", "contract", "excel_row", actual_col, comment_col]].copy()
            temp["metric"] = metric
            temp["actual"] = temp[actual_col]
            temp["comment"] = temp[comment_col]
            rows.extend(temp[["category", "contract", "excel_row", "metric", "actual", "comment"]].to_dict("records"))
        result = pd.DataFrame(rows).sort_values("actual", ascending=True).head(spec.top_n)
        lines = [f"Lowest {len(result)} {spec.period.replace('_', ' ')} actual item(s) ({UNIT}):"]
        for _, r in result.iterrows():
            lines.append(
                f"- {r['contract']} | Category: {r['category']} | Metric: {str(r['metric']).title()} | "
                f"Actual: {fmt_money(float(r['actual']))} | Comment: {safe_snippet(r['comment']) or 'No comment'}"
            )
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection=f"Classified as lowest/bottom actual ranking and used fixed {spec.period} actual columns only.",
            confidence="high",
            rows_used=len(df),
            data=result.to_dict("records"),
        )

    def _total(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}
        for metric in self.metric_list(spec):
            actual_col = self.actual_col(spec.period, metric)
            compare_col, compare_name = self.compare_col_for(spec.period, metric, spec.comparator)
            var_col, comparator = self.variance_col_for(spec.period, metric, spec.comparator)
            if not compare_col or not var_col:
                return self._unknown(spec, f"The requested comparator is not supported for {spec.period} {metric} under the strict rules.")
            row = {
                "metric": metric,
                "period": spec.period,
                "actual": float(df[actual_col].sum()),
                "comparator_name": compare_name,
                "comparator": float(df[compare_col].sum()),
                "variance": float(df[var_col].sum()),
            }
            rows.append(row)
            columns_used[metric] = self.columns_used_for(spec.period, metric)
        lines = [f"Total {spec.period.replace('_', ' ')} result ({UNIT}):"]
        for r in rows:
            lines.append(
                f"- {str(r['metric']).title()}: Actual {fmt_money(r['actual'])} vs {r['comparator_name']} "
                f"{fmt_money(r['comparator'])}; Variance {fmt_money(r['variance'])}"
            )
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection=f"Calculated totals by summing CT-Narrative rows after applying the requested Column B/C scope.",
            confidence="high",
            rows_used=len(df),
            data=rows,
        )

    def _actual_vs_comparator(self, spec: QuerySpec) -> AgentAnswer:
        return self._total(spec)

    def _category_breakdown(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}
        for metric in self.metric_list(spec):
            actual_col = self.actual_col(spec.period, metric)
            compare_col, compare_name = self.compare_col_for(spec.period, metric, spec.comparator)
            var_col, comparator = self.variance_col_for(spec.period, metric, spec.comparator)
            if not compare_col or not var_col:
                return self._unknown(spec, f"The requested comparator is not supported for {spec.period} {metric} under the strict rules.")
            grouped = df.groupby("category", dropna=False).agg(
                actual=(actual_col, "sum"),
                comparator=(compare_col, "sum"),
                variance=(var_col, "sum"),
                contract_count=("contract", "count"),
            ).reset_index()
            grouped["metric"] = metric
            grouped["comparator_name"] = compare_name
            rows.extend(grouped.to_dict("records"))
            columns_used[metric] = self.columns_used_for(spec.period, metric)
        result = pd.DataFrame(rows)
        result = result.assign(abs_variance=result["variance"].abs()).sort_values("abs_variance", ascending=False)
        result = result.head(spec.top_n if "top" in spec.question.lower() else 25)
        lines = [f"{spec.period.replace('_', ' ').title()} breakdown by Column B category ({UNIT}):"]
        for _, r in result.iterrows():
            lines.append(
                f"- {r['category']} | Metric: {str(r['metric']).title()} | Actual {fmt_money(float(r['actual']))} | "
                f"{r['comparator_name']} {fmt_money(float(r['comparator']))} | Variance {fmt_money(float(r['variance']))} | "
                f"Contracts: {int(r['contract_count'])}"
            )
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection="Grouped only by Column B category/country from CT-Narrative and used fixed metric columns.",
            confidence="high",
            rows_used=len(df),
            data=result.drop(columns=["abs_variance"], errors="ignore").to_dict("records"),
        )

    def _comments(self, spec: QuerySpec) -> AgentAnswer:
        df = self.apply_scope(spec)
        if df.empty:
            return self._unknown(spec, "No matching rows were found for the requested scope.")
        rows: list[dict[str, Any]] = []
        columns_used: dict[str, Any] = {}
        for metric in self.metric_list(spec):
            comment_col = self.comment_col(spec.period, metric)
            var_col, comparator = self.variance_col_for(spec.period, metric, spec.comparator)
            if not var_col:
                return self._unknown(spec, f"The requested comparator is not supported for {spec.period} {metric} under the strict rules.")
            temp = df[["category", "contract", "excel_row", var_col, comment_col]].copy()
            temp["metric"] = metric
            temp["variance"] = temp[var_col]
            temp["comment"] = temp[comment_col]
            temp = temp[temp["comment"].map(lambda x: bool(clean_text(x)))]
            rows.extend(temp[["category", "contract", "excel_row", "metric", "variance", "comment"]].to_dict("records"))
            columns_used[metric] = self.columns_used_for(spec.period, metric)
        if not rows:
            return self._unknown(spec, "No comments were populated in the required comment columns for the requested scope/metric.")
        result = pd.DataFrame(rows).assign(abs_variance=lambda d: d["variance"].abs()).sort_values("abs_variance", ascending=False).head(spec.top_n)
        lines = [f"Top {len(result)} CT-Narrative comment(s) by variance size:"]
        for _, r in result.iterrows():
            lines.append(
                f"- {r['contract']} | Category: {r['category']} | Metric: {str(r['metric']).title()} | "
                f"Variance {fmt_money(float(r['variance']))} | Comment: {safe_snippet(r['comment'], 300)}"
            )
        return AgentAnswer(
            can_answer=True,
            answer="\n".join(lines),
            question_spec=spec,
            columns_used=columns_used,
            reflection="Used only comment columns AO/AP/AQ as required, plus the relevant fixed variance column for ranking.",
            confidence="high",
            rows_used=len(df),
            data=result.drop(columns=["abs_variance"], errors="ignore").to_dict("records"),
        )

    def _unknown(self, spec: QuerySpec | None, reason: str) -> AgentAnswer:
        return AgentAnswer(
            can_answer=False,
            answer="I don't know based on the CT-Narrative sheet.",
            question_spec=spec,
            columns_used={},
            reflection=reason,
            confidence="low",
            rows_used=0,
            data=[],
        )
