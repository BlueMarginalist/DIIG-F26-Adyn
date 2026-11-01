"""Optional read-only Postgres access. Uses the existing ADYN_POSTGRES_* names."""
import os
import pandas as pd


class Database:
    def __init__(self, env_file=None):
        # Imports stay here so synthetic examples work without database packages.
        import psycopg
        from dotenv import load_dotenv
        if env_file is not None:
            load_dotenv(env_file, override=False)
        names = ["HOST", "DB", "USER", "PASSWORD"]
        missing = [f"ADYN_POSTGRES_{n}" for n in names
                   if not os.getenv(f"ADYN_POSTGRES_{n}")]
        if missing:
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        self.conn = psycopg.connect(
            host=os.environ["ADYN_POSTGRES_HOST"],
            port=os.environ.get("ADYN_POSTGRES_PORT", "5432"),
            dbname=os.environ["ADYN_POSTGRES_DB"],
            user=os.environ["ADYN_POSTGRES_USER"],
            password=os.environ["ADYN_POSTGRES_PASSWORD"],
            options="-c default_transaction_read_only=on",
        )
        self.conn.autocommit = True

    def query(self, sql, params=None):
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col.name for col in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
