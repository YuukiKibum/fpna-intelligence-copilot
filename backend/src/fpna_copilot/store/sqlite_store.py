from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


FACT_FINANCE_COLUMNS = [
    "upload_id",
    "file_name",
    "sheet_name",
    "period",
    "year",
    "month",
    "period_type",
    "entity_type",
    "entity_name",
    "contract",
    "category",
    "country",
    "sector",
    "metric",
    "scenario",
    "value",
    "currency",
    "unit",
    "comment",
    "excel_row",
]


DIM_UPLOAD_COLUMNS = [
    "upload_id",
    "file_name",
    "sheet_name",
    "period",
    "year",
    "month",
]


DIM_ENTITY_COLUMNS = [
    "entity_name",
    "entity_type",
    "contract",
    "category",
    "country",
    "sector",
]


DIM_METRIC_COLUMNS = [
    "metric",
]


DIM_PERIOD_COLUMNS = [
    "period",
    "year",
    "month",
    "period_type",
]


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "fpna_copilot.db"


class SQLiteStore:
    """
    Persistent database store using SQLite.

    SQLite stores normalized finance rows.
    Pandas still performs finance calculations.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def create_tables(self) -> None:
        """
        Create tables if missing and add new columns if the DB already exists.
        """

        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fact_finance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id TEXT NOT NULL,
                    file_name TEXT,
                    sheet_name TEXT,
                    period TEXT,
                    year INTEGER,
                    month TEXT,
                    period_type TEXT,
                    entity_type TEXT,
                    entity_name TEXT,
                    contract TEXT,
                    category TEXT,
                    country TEXT,
                    sector TEXT,
                    metric TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    value REAL NOT NULL,
                    currency TEXT,
                    unit TEXT,
                    comment TEXT,
                    excel_row INTEGER
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dim_upload (
                    upload_id TEXT,
                    file_name TEXT,
                    sheet_name TEXT,
                    period TEXT,
                    year INTEGER,
                    month TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dim_entity (
                    entity_name TEXT,
                    entity_type TEXT,
                    contract TEXT,
                    category TEXT,
                    country TEXT,
                    sector TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dim_metric (
                    metric TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dim_period (
                    period TEXT,
                    year INTEGER,
                    month TEXT,
                    period_type TEXT
                )
                """
            )

            conn.commit()

        self._ensure_columns()

    def _ensure_columns(self) -> None:
        """
        Add missing columns to existing SQLite tables.

        This helps when we change schema during development.
        """

        required_columns = {
            "fact_finance": {
                "upload_id": "TEXT",
                "file_name": "TEXT",
                "sheet_name": "TEXT",
                "period": "TEXT",
                "year": "INTEGER",
                "month": "TEXT",
                "period_type": "TEXT",
                "entity_type": "TEXT",
                "entity_name": "TEXT",
                "contract": "TEXT",
                "category": "TEXT",
                "country": "TEXT",
                "sector": "TEXT",
                "metric": "TEXT",
                "scenario": "TEXT",
                "value": "REAL",
                "currency": "TEXT",
                "unit": "TEXT",
                "comment": "TEXT",
                "excel_row": "INTEGER",
            },
            "dim_upload": {
                "upload_id": "TEXT",
                "file_name": "TEXT",
                "sheet_name": "TEXT",
                "period": "TEXT",
                "year": "INTEGER",
                "month": "TEXT",
            },
            "dim_entity": {
                "entity_name": "TEXT",
                "entity_type": "TEXT",
                "contract": "TEXT",
                "category": "TEXT",
                "country": "TEXT",
                "sector": "TEXT",
            },
            "dim_metric": {
                "metric": "TEXT",
            },
            "dim_period": {
                "period": "TEXT",
                "year": "INTEGER",
                "month": "TEXT",
                "period_type": "TEXT",
            },
        }

        with self.connect() as conn:
            for table_name, columns in required_columns.items():
                existing = {
                    row[1]
                    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                }

                for column_name, column_type in columns.items():
                    if column_name not in existing:
                        conn.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                        )

            conn.commit()

    def add_fact_rows(self, rows: list[dict[str, Any]]) -> None:
        """
        Add normalized finance rows into SQLite.
        """

        if not rows:
            return

        df = pd.DataFrame(rows)

        for column in FACT_FINANCE_COLUMNS:
            if column not in df.columns:
                df[column] = None

        df = df[FACT_FINANCE_COLUMNS]

        with self.connect() as conn:
            df.to_sql(
                "fact_finance",
                conn,
                if_exists="append",
                index=False,
            )

        self.refresh_dimensions()

    def read_table(self, table_name: str) -> pd.DataFrame:
        """
        Read a full table from SQLite into pandas.
        """

        allowed_tables = {
            "fact_finance",
            "dim_upload",
            "dim_entity",
            "dim_metric",
            "dim_period",
        }

        if table_name not in allowed_tables:
            raise ValueError(f"Unknown table: {table_name}")

        with self.connect() as conn:
            return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
        """
        Run a trusted SELECT query and return pandas DataFrame.

        Do not pass raw LLM-generated SQL here.
        """

        normalized_sql = sql.strip().lower()

        if not normalized_sql.startswith("select"):
            raise ValueError("Only SELECT queries are allowed through query().")

        with self.connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def clear_all(self) -> None:
        """
        Delete all data from all tables.
        """

        with self.connect() as conn:
            for table in [
                "fact_finance",
                "dim_upload",
                "dim_entity",
                "dim_metric",
                "dim_period",
            ]:
                conn.execute(f"DELETE FROM {table}")
            conn.commit()

    def is_empty(self) -> bool:
        """
        Return True if fact_finance has no rows.
        """

        with self.connect() as conn:
            result = conn.execute("SELECT COUNT(*) FROM fact_finance").fetchone()

        count = result[0] if result else 0
        return count == 0

    def refresh_dimensions(self) -> None:
        """
        Rebuild dimension tables from fact_finance.
        """

        fact_df = self.read_table("fact_finance")

        with self.connect() as conn:
            for table in [
                "dim_upload",
                "dim_entity",
                "dim_metric",
                "dim_period",
            ]:
                conn.execute(f"DELETE FROM {table}")

            if fact_df.empty:
                conn.commit()
                return

            (
                fact_df[DIM_UPLOAD_COLUMNS]
                .drop_duplicates()
                .to_sql("dim_upload", conn, if_exists="append", index=False)
            )

            (
                fact_df[DIM_ENTITY_COLUMNS]
                .drop_duplicates()
                .to_sql("dim_entity", conn, if_exists="append", index=False)
            )

            (
                fact_df[DIM_METRIC_COLUMNS]
                .drop_duplicates()
                .to_sql("dim_metric", conn, if_exists="append", index=False)
            )

            (
                fact_df[DIM_PERIOD_COLUMNS]
                .drop_duplicates()
                .to_sql("dim_period", conn, if_exists="append", index=False)
            )

            conn.commit()


store = SQLiteStore()