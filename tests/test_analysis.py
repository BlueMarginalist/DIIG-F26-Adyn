import pandas as pd
import pytest

from funnel_pkg import Config, FunnelEDA, clean
from funnel_pkg.demo import DemoData


def test_funnel_is_monotonic_after_paid(eda):
    f = eda.funnel().set_index("stage")["customers"]
    assert f["Paid order"] >= f["Kit shipped (left Allied)"] >= f["Result created"] >= f["Result viewed"]


def test_bulk_accounts_are_excluded_from_the_funnel(eda):
    assert len(eda.bulk_accounts) > 0
    assert (eda.customers["n_orders"] < Config().bulk_account_min_orders).all()


def test_largest_drop_names_a_stage(eda):
    d = eda.largest_drop()
    assert d["stage"] in set(eda.funnel()["stage"]) and d["lost"] > 0


def test_stage_gaps_flag_negative_days():
    raw = DemoData(n=50).customers_raw.copy()
    raw["lab_received"] = raw["shipped"] - pd.Timedelta(3, unit="D")  # lab "before" shipping everywhere
    class D:  # minimal stand-in
        customers_raw = raw
    gaps = FunnelEDA(D()).stage_gaps().set_index(["from", "to"])
    assert gaps.loc[("shipped", "lab_received"), "pct_negative"] == 100.0


def test_rate_tables_flag_small_groups(eda):
    for table in eda.ship_rates().values():
        assert (table["small_n"] == (table["paid_customers"] < eda.cfg.small_n)).all()
    assert set(eda.result_rates()) == {"paid_year", "age", "state", "gift_redeemer"}


def test_replacement_buckets_collapse_tail():
    b = clean.replacement_buckets(pd.DataFrame({"n_rep": [1, 2, 5, 9], "customers": [10, 4, 2, 1]}))
    assert list(b["bucket"]) == ["1", "2", "3", "4+"] and list(b["customers"]) == [10, 4, 0, 3]


def test_reason_classes_sum_to_total(eda):
    c = eda.replacement_reason_classes()
    assert c["records"].sum() == int(eda.data.replacement_reason_counts.iloc[0]["total"])


def test_cohort_burst_months_stand_out(eda):
    c = eda.cohort_by_month("2023-01-01", "2024-01-01").set_index(pd.to_datetime(eda.cohort_by_month()["paid_month"]).dt.strftime("%Y-%m"))
    assert c.loc["2023-02", "paid"] > 2 * c["paid"].median()
    assert c.loc["2023-02", "pct_shipped"] < c["pct_shipped"].median()


def test_tables_are_all_dataframes_and_contain_no_identifiers(eda):
    t = eda.tables()
    assert len(t) >= 30
    for name, table in t.items():
        assert isinstance(table, pd.DataFrame), name
        assert not {"email", "first_name", "last_name", "phone", "street"} & set(table.columns), name
    assert "customer_id" not in set().union(*[set(x.columns) for x in t.values()])


def test_missing_columns_give_a_clear_error():
    with pytest.raises(ValueError, match="Required columns missing"):
        clean.prepare_customers(pd.DataFrame({"customer_id": [1]}))


def test_prepare_does_not_modify_its_input():
    raw = DemoData(n=40).customers_raw
    before = raw.copy()
    clean.prepare_customers(raw)
    pd.testing.assert_frame_equal(raw, before)
