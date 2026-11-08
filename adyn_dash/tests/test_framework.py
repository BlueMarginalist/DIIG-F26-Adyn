"""Tests for the shared framework: config, sources, backends, module registry, privacy guard and build."""
import json

import pandas as pd
import pytest

from adyn_dash import AnalysisModule, Config, DataStore, DemoBackend, PrivacyError, Source, chart
from adyn_dash.build import build, to_records
from adyn_dash.modules import ALL_MODULES


class FakeBackend:
    """Counts fetches so the cache can be checked."""

    def __init__(self, tables):
        self.tables, self.calls = tables, []

    def fetch(self, source, cfg):
        self.calls.append(source.key)
        return self.tables[source.name].copy()

    def close(self):
        pass


class Toy(AnalysisModule):
    name, title, owner = "toy", "Toy", "Test"
    sources = (Source("toy", "events", ("day", "n")),)

    @chart("Events per day", "bar", x="day", y="n", note="a note")
    def per_day(self):
        return self.data("events")

    @chart("Leaks ids", "table")
    def leaky(self):
        return pd.DataFrame({"customer_id": ["a"], "n": [1]})

    @chart("Too long", "table")
    def long_table(self):
        return pd.DataFrame({"n": range(6000)})

    def helper(self):  # not a chart
        return 1


def test_every_sql_file_exists_for_every_declared_source():
    cfg = Config()
    for klass in ALL_MODULES.values():
        for source in klass.sources:
            assert source.sql(cfg).strip(), source.key


def test_chart_discovery_ignores_helpers_and_sorts():
    assert [c.name for c in Toy.charts()] == ["leaky", "long_table", "per_day"]
    spec = next(c for c in Toy.charts() if c.name == "per_day")
    assert (spec.mark, spec.x, spec.y, spec.note) == ("bar", "day", "n", "a note")


def test_store_caches_each_source_once_and_refresh_clears():
    backend = FakeBackend({"events": pd.DataFrame({"day": [1], "n": [2]})})
    store = DataStore(backend)
    toy = Toy(store)
    toy.run("per_day"); toy.run("per_day")
    assert backend.calls == ["toy.events"]
    store.refresh(); toy.run("per_day")
    assert backend.calls == ["toy.events", "toy.events"]


def test_missing_declared_column_is_reported_by_source_name():
    store = DataStore(FakeBackend({"events": pd.DataFrame({"day": [1]})}))
    with pytest.raises(ValueError, match="toy.events is missing columns: n"):
        Toy(store).run("per_day")


def test_privacy_guard_blocks_ids_and_long_tables():
    toy = Toy(DataStore(FakeBackend({"events": pd.DataFrame({"day": [1], "n": [2]})})))
    with pytest.raises(PrivacyError, match="customer_id"):
        toy.run("leaky")
    with pytest.raises(PrivacyError, match="6000 rows"):
        toy.run("long_table")


def test_sql_override_dir_replaces_bundled_query(tmp_path):
    (tmp_path / "virtual_care").mkdir()
    (tmp_path / "virtual_care" / "appointments.sql").write_text("select 1 as custom", encoding="utf-8")
    source = ALL_MODULES["virtual_care"].sources[0]
    assert source.sql(Config(sql_override_dir=str(tmp_path))).strip() == "select 1 as custom"
    assert "from appointments" in source.sql(Config()).lower()


def test_query_params_cover_every_named_parameter():
    import re
    cfg, names = Config(), set(Config().params())
    for klass in ALL_MODULES.values():
        for source in klass.sources:
            for used in set(re.findall(r"%\((\w+)\)s", source.sql(cfg))):
                assert used in names, f"{source.key} uses unknown parameter {used}"


def test_to_records_is_json_safe():
    table = pd.DataFrame({"a": [1.5, float("nan")], "d": [pd.Timestamp("2024-01-02"), pd.NaT],
                          "b": [True, False], "p": pd.period_range("2024-01", periods=2, freq="M")})
    text = json.dumps(to_records(table))
    assert "NaN" not in text and "2024-01-02" in text


def test_build_demo_writes_manifest_and_files(tmp_path):
    manifest = build(out=str(tmp_path), demo=True, cfg=Config(as_of="2026-11-01"))
    assert manifest["source"] == "demo"
    assert {c["module"] for c in manifest["charts"]} == set(ALL_MODULES)
    failed = [c["id"] for c in manifest["charts"] if c["status"] != "ok"]
    assert not failed, failed
    for entry in manifest["charts"]:
        data = json.loads((tmp_path / entry["file"]).read_text(encoding="utf-8"))
        assert len(data) == entry["rows"] > 0, entry["id"]
        assert set(data[0]) == set(entry["columns"])
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["charts"]


def test_build_records_a_failing_chart_and_continues(tmp_path, monkeypatch):
    from adyn_dash.modules.virtual_care import VirtualCare

    def monthly_visits(self):
        raise RuntimeError("bad query")
    monkeypatch.setattr(VirtualCare, "monthly_visits", chart("Monthly visits", "line", x="month", y="visits")(monthly_visits))
    manifest = build(["virtual_care"], out=str(tmp_path), demo=True)
    status = {c["id"]: c for c in manifest["charts"]}
    assert status["virtual_care.monthly_visits"]["status"] == "error"
    assert "bad query" in status["virtual_care.monthly_visits"]["error"]
    assert status["virtual_care.visit_frequency"]["status"] == "ok"


def test_chart_specs_point_at_real_columns():
    """Every x / y / y2 / color / filter named in a spec must exist in the table the chart returns."""
    store = DataStore(DemoBackend(list(ALL_MODULES.values())), Config(as_of="2026-11-01"))
    for klass in ALL_MODULES.values():
        module = klass(store)
        for spec in klass.charts():
            table = module.run(spec.name)
            for field in (spec.x, spec.y, spec.y2, spec.color, *spec.filters):
                if field:
                    assert field in table.columns, f"{klass.name}.{spec.name}: '{field}' not in {list(table.columns)}"
