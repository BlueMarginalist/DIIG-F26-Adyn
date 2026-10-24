import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


class Database:
    """Read-only connection to the Adyn Postgres DB.

    Credentials come from setenv_STAGING.sh (never from code). By default the
    file is looked for one folder above the working directory.
    """

    def __init__(self, env_file=None):
        env_file = Path(env_file) if env_file else Path.cwd().parent / "setenv_STAGING.sh"
        load_dotenv(env_file)
        self.conn = psycopg.connect(
            host=os.environ["ADYN_POSTGRES_HOST"],
            port=os.environ.get("ADYN_POSTGRES_PORT", "5432"),
            dbname=os.environ["ADYN_POSTGRES_DB"],
            user=os.environ["ADYN_POSTGRES_USER"],
            password=os.environ["ADYN_POSTGRES_PASSWORD"],
        )
        self.conn.autocommit = True

    def query(self, sql, params=None):
        """Run a SQL query and return the result as a DataFrame."""
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)

    def close(self):
        self.conn.close()
