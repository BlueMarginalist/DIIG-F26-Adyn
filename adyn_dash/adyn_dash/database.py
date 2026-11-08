"""Where the data comes from: the live Postgres database, or synthetic demo data.

Both backends answer the same question (`fetch(source, cfg)`), so the analyses never know which one they
are talking to. Changing the connection is the only step needed to point the dashboard at real data.
"""
from __future__ import annotations

import os
from decimal import Decimal

import pandas as pd

from .config import Config
from .source import Source


class PostgresBackend:
    """Read-only Postgres connection. Credentials come from <prefix>_HOST/_PORT/_DB/_USER/_PASSWORD."""

    def __init__(self, cfg: Config | None = None, env_file=None):
        cfg = cfg or Config()
        # Imports stay here so the demo and the tests work without database packages.
        import psycopg
        if env_file is not None:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        prefix = cfg.env_prefix
        missing = [f"{prefix}_{n}" for n in ("HOST", "DB", "USER", "PASSWORD") if not os.getenv(f"{prefix}_{n}")]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        self.conn = psycopg.connect(
            host=os.environ[f"{prefix}_HOST"], port=os.environ.get(f"{prefix}_PORT", "5432"),
            dbname=os.environ[f"{prefix}_DB"], user=os.environ[f"{prefix}_USER"],
            password=os.environ[f"{prefix}_PASSWORD"],
            options="-c default_transaction_read_only=on", connect_timeout=cfg.connect_timeout,
        )
        self.conn.autocommit = True

    def fetch(self, source: Source, cfg: Config) -> pd.DataFrame:
        sql = source.sql(cfg)
        # Only queries with named parameters are interpolated, so literal % signs elsewhere are safe.
        params = cfg.params() if "%(" in sql else None
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col.name for col in cursor.description]
            return _tidy(pd.DataFrame(cursor.fetchall(), columns=columns))

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DemoBackend:
    """Synthetic data. Each module supplies its own demo tables, named like its sources."""

    def __init__(self, modules):
        self._modules = {m.name: m for m in modules}
        self._demo: dict = {}

    def fetch(self, source: Source, cfg: Config) -> pd.DataFrame:
        if source.module not in self._demo:
            self._demo[source.module] = self._modules[source.module].demo_sources(cfg)
        tables = self._demo[source.module]
        if source.name not in tables:
            raise KeyError(f"No demo data for source {source.key}")
        return tables[source.name].copy()

    def close(self) -> None:
        pass


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Decimal columns from Postgres become floats."""
    for c in df.columns:
        if df[c].dtype == object:
            vals = df[c].dropna()
            if len(vals) and all(isinstance(v, (Decimal, int, float)) and not isinstance(v, bool) for v in vals):
                df[c] = pd.to_numeric(df[c])
    return df
