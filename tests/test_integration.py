"""End-to-end against a real Postgres. Skipped unless ADYN_TEST_PG=1 and ADYN_POSTGRES_* point at an EMPTY SCRATCH
database you can write to. The test wipes the public schema of that database, so never aim it at real data."""
import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ADYN_TEST_PG") != "1", reason="set ADYN_TEST_PG=1 to run")


@pytest.fixture()
def pg():
    import psycopg
    from seed import MIN_SCHEMA, seed
    conn = psycopg.connect(host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
                           dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
                           password=os.environ.get("ADYN_POSTGRES_PASSWORD", ""), autocommit=True)
    conn.execute("drop schema public cascade")
    conn.execute("create schema public")
    conn.execute(MIN_SCHEMA)
    truth = seed(conn)
    yield truth
    conn.execute("drop schema public cascade")
    conn.execute("create schema public")
    conn.close()


def test_real_queries_match_ground_truth(pg):
    from funnel_pkg import Database, FunnelData, FunnelEDA
    db = Database()
    try:
        data = FunnelData(db)
        eda = FunnelEDA(data)
        f = eda.funnel().set_index("stage")["customers"]
        assert f["Paid order"] == pg["paid"]
        assert f["Kit shipped (left Allied)"] == pg["shipped"]
        assert f["Result created"] == pg["result"]
        assert f["Result approved"] == pg["approved"]
        assert f["Result viewed"] == pg["viewed"]
        per = eda.replacements_per_customer()
        assert int((per["n_rep"] * per["customers"]).sum()) == pg["replacement_orders"]
        tables = eda.tables()
        assert len(tables) >= 30
        assert "error" not in data.date_quality.columns
    finally:
        db.close()


def test_connection_is_read_only(pg):
    from funnel_pkg import Database
    db = Database()
    try:
        with pytest.raises(Exception, match="read-only"):
            db.query("delete from customers")
    finally:
        db.close()


@pytest.mark.skipif(os.environ.get("ADYN_TEST_REAL_SCHEMA") != "1",
                    reason="set ADYN_TEST_REAL_SCHEMA=1 with a database holding the full adyn schema (tables may be empty)")
def test_exploration_queries_run_on_the_full_schema():
    from funnel_pkg import Database, FunnelData
    db = Database()
    try:
        data = FunnelData(db)
        for group in ("profile", "diagnostics"):
            failed = {k: v for k, v in data.run_diagnostics(group).items() if isinstance(v, str)}
            assert not failed, failed
        assert "error" not in data.date_quality.columns
    finally:
        db.close()
