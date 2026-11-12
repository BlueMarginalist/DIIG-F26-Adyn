import re

import pytest

from funnel_pkg import Config, Database, FunnelData, queries

EXTRA = {"cohort_start": "2023-01-01", "cohort_end": "2024-01-01"}


def all_queries():
    qs = {n: v for n, v in vars(queries).items() if n.isupper() and isinstance(v, str) and "select" in v.lower()}
    qs.update({f"PROFILE:{k}": v for k, v in queries.PROFILE.items()})
    qs.update({f"DIAG:{k}": v for k, v in queries.DIAGNOSTICS.items()})
    qs["DATE_QUALITY"] = queries.date_quality_sql("orders", "date_order_paid")
    return qs


def test_every_placeholder_is_provided_by_config():
    provided = set(Config().params()) | set(EXTRA)
    for name, q in all_queries().items():
        used = set(re.findall(r"%\((\w+)\)s", q))
        assert used <= provided, f"{name}: {used - provided}"


def test_no_stray_percent_signs():
    for name, q in all_queries().items():
        assert "%" not in re.sub(r"%\(\w+\)s", "", q), name


def test_queries_are_read_only_and_aggregate():
    for name, q in all_queries().items():
        low = q.lower()
        assert not re.search(r"\b(insert|update|delete|drop|alter|truncate|create)\b", low), name
        assert not re.search(r"\b(first_name|last_name|phone|street)\b", low.split("from", 1)[0]), name


def test_date_quality_rejects_bad_identifiers():
    with pytest.raises(ValueError):
        queries.date_quality_sql("orders; drop table x", "a")


def test_postgres_syntax_with_pglast():
    pglast = pytest.importorskip("pglast")
    params = {**Config().params(), **EXTRA}
    for name, q in all_queries().items():
        if name.endswith("_BASE"):
            continue
        text = re.sub(r"%\((\w+)\)s", lambda m: "array['x']" if isinstance(params[m.group(1)], list) else "'x'", q)
        pglast.parse_sql(text)


def test_missing_environment_variables_give_a_clear_error(monkeypatch):
    for v in ("HOST", "DB", "USER", "PASSWORD", "PORT"):
        monkeypatch.delenv(f"ADYN_POSTGRES_{v}", raising=False)
    with pytest.raises(ValueError, match="ADYN_POSTGRES_HOST"):
        Database()


class FakeDb:
    def __init__(self):
        self.calls = []

    def query(self, sql, params=None):
        import pandas as pd
        self.calls.append((sql, params))
        return pd.DataFrame({"x": [1]})


def test_data_runs_each_query_once_until_refresh():
    db = FakeDb()
    d = FunnelData(db)
    d.kit_outcomes, d.kit_outcomes
    assert len(db.calls) == 1
    d.refresh()
    d.kit_outcomes
    assert len(db.calls) == 2


def test_params_passed_only_when_the_query_uses_them():
    db = FakeDb()
    d = FunnelData(db)
    d.sample_status_by_kind          # no placeholders
    d.kit_outcomes                   # has placeholders
    assert db.calls[0][1] is None and "replacement_pattern" in db.calls[1][1]


def test_cohort_is_cached_per_date_range():
    db = FakeDb()
    d = FunnelData(db)
    d.cohort_by_month("2023-01-01", "2024-01-01"); d.cohort_by_month("2023-01-01", "2024-01-01"); d.cohort_by_month("2022-01-01", "2023-01-01")
    assert len(db.calls) == 2


def test_diagnostic_failure_is_returned_not_raised():
    class Bad:
        def query(self, *a, **k):
            raise RuntimeError("boom\nmore")
    out = FunnelData(Bad()).run_diagnostics("profile")
    assert all(str(v).startswith("ERROR: boom") for v in out.values())
