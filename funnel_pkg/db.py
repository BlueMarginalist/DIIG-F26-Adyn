"""Read-only Postgres access. Uses the existing ADYN_POSTGRES_* names (never credentials in code)."""
import os
import re
from decimal import Decimal

import pandas as pd

# Columns that directly identify a person; never exported by export_tables().
SKIP_COLUMNS = re.compile(r"email|phone|first_?name|last_?name|full_?name|street|line1|line2|address1|address2", re.I)

PROJECT_TABLES = ["customers", "profilecompletions", "orders", "orderstatuses", "shipments",
                  "shipmentstatuses", "samples", "resultvalues", "couponorders", "paymentissues"]


class Database:
    """Read-only connection. Credentials come from environment variables, optionally loaded from an env file.

    Variables: <prefix>_HOST, _PORT (default 5432), _DB, _USER, _PASSWORD, with prefix ADYN_POSTGRES by default.
    """

    def __init__(self, env_file=None, env_prefix="ADYN_POSTGRES"):
        # Imports stay here so the demo and the tests work without database packages.
        import psycopg
        if env_file is not None:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        missing = [f"{env_prefix}_{n}" for n in ("HOST", "DB", "USER", "PASSWORD")
                   if not os.getenv(f"{env_prefix}_{n}")]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        self.conn = psycopg.connect(
            host=os.environ[f"{env_prefix}_HOST"],
            port=os.environ.get(f"{env_prefix}_PORT", "5432"),
            dbname=os.environ[f"{env_prefix}_DB"],
            user=os.environ[f"{env_prefix}_USER"],
            password=os.environ[f"{env_prefix}_PASSWORD"],
            options="-c default_transaction_read_only=on",
            connect_timeout=10,
        )
        self.conn.autocommit = True

    def query(self, sql, params=None):
        """Run a SQL query and return the result as a DataFrame (Decimal columns become floats)."""
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col.name for col in cursor.description]
            return _tidy(pd.DataFrame(cursor.fetchall(), columns=columns))

    # ---- looking around (test_connection.py, explore.py, pull_tables.py) ---------------------------
    def tables(self):
        """Tables the connection can see (also proves the credentials work)."""
        return self.query("""select table_schema, table_name from information_schema.tables
                             where table_schema not in ('pg_catalog', 'information_schema') order by 1, 2""")

    def columns(self, table):
        return self.query("""select column_name, data_type from information_schema.columns
                             where table_schema='public' and table_name=%(t)s order by ordinal_position""",
                          {"t": table})

    def row_count(self, table):
        if not re.fullmatch(r"[a-z_0-9]+", table):
            raise ValueError("table must be a plain lowercase identifier")
        return int(self.query(f'select count(*) as n from public."{table}"').iloc[0]["n"])

    def export_schema(self, path):
        """Write schema | table | column | type lines for every table."""
        d = self.query("""select table_schema, table_name, column_name, data_type from information_schema.columns
                          where table_schema not in ('pg_catalog','information_schema')
                          order by 1,2,ordinal_position""")
        with open(path, "w") as f:
            for row in d.itertuples(index=False):
                f.write(" | ".join(row) + "\n")

    def export_tables(self, out_dir, tables=PROJECT_TABLES):
        """Copy each table to <out_dir>/<table>.csv, leaving out columns that identify a person.

        Returns a summary (table, rows, columns exported, columns skipped)."""
        os.makedirs(out_dir, exist_ok=True)
        summary = []
        for t in tables:
            cols = list(self.columns(t)["column_name"])
            if not cols:
                summary.append({"table": t, "rows": None, "exported": 0, "skipped": "NOT FOUND"})
                continue
            keep = [c for c in cols if not SKIP_COLUMNS.search(c)]
            dropped = [c for c in cols if SKIP_COLUMNS.search(c)]
            collist = ", ".join(f'"{c}"' for c in keep)
            with self.conn.cursor() as cursor, open(os.path.join(out_dir, f"{t}.csv"), "wb") as f:
                with cursor.copy(f'COPY (select {collist} from public."{t}") TO STDOUT WITH CSV HEADER') as copy:
                    for chunk in copy:
                        f.write(bytes(chunk))
            summary.append({"table": t, "rows": self.row_count(t), "exported": len(keep),
                            "skipped": ", ".join(dropped)})
        return pd.DataFrame(summary)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _tidy(df):
    for c in df.columns:
        if df[c].dtype == object:
            vals = df[c].dropna()
            if len(vals) and all(isinstance(v, (Decimal, int, float)) and not isinstance(v, bool) for v in vals):
                df[c] = pd.to_numeric(df[c])
    return df
