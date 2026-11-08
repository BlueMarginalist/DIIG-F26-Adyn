"""Behaviour checks for the ported analysis logic that the demo build alone would not catch."""
import pandas as pd
import pytest

from adyn_dash.lib.biomarkers import analysis as bio_analysis, clean as bio_clean
from adyn_dash.lib.funnel import clean as funnel_clean
from adyn_dash.lib.prescriptions import calc


# ---- prescriptions (Morgan) ---------------------------------------------------------------------
def test_delay_histogram_counts_and_reports_exclusions():
    d = pd.DataFrame({"s": pd.to_datetime(["2024-01-01"] * 4 + [None]),
                      "e": pd.to_datetime(["2024-01-02", "2024-01-03", "2023-12-31", "2024-01-02", "2024-01-02"])})
    out = calc.delay_histogram(d, "s", "e", unit="days", nonnegative=True, binwidth=1)
    assert out["orders"].sum() == 3
    assert out.attrs["excluded_missing"] == 1 and out.attrs["excluded_negative"] == 1


def test_state_counts_group_unrecognized_and_missing():
    d = pd.DataFrame({"state": ["ca", "CA", "ZZ", " ", None, "TX"]})
    out = calc.shipment_state_counts(d).set_index("state")["shipments"]
    assert out["CA"] == 2 and out["TX"] == 1 and out["(unrecognized)"] == 1 and out["(missing)"] == 2


def test_conflicting_dates_of_birth_raise():
    d = pd.DataFrame({"patient_id": ["a", "a"], "customer_dob": ["1990-01-01", "1991-01-01"]})
    with pytest.raises(ValueError, match="Conflicting DOBs"):
        calc.customer_ages(d)


def test_age_is_birthday_aware_and_future_dob_is_separate():
    d = pd.DataFrame({"patient_id": ["a", "b", "c"], "customer_dob": ["1990-06-15", "1990-06-14", "2030-01-01"]})
    ages = calc.customer_ages(d, as_of="2024-06-14").set_index("patient_id")["age"]
    assert ages["a"] == 33 and ages["b"] == 34
    groups = calc.age_groups(calc.customer_ages(d, as_of="2024-06-14")).set_index("age_group")["patients"]
    assert groups["future date of birth"] == 1


def test_unrecognized_flag_value_raises_instead_of_guessing():
    d = pd.DataFrame({"f": ["True", "maybe"]})
    with pytest.raises(ValueError, match="Unrecognized"):
        calc.flag_counts(d, {"f": "F"})


def test_order_status_blank_counts_as_missing():
    out = calc.order_status_summary(pd.DataFrame({"status": ["a", "", None, "a"]})).set_index("status")
    assert out.loc["(missing)", "n_orders"] == 2 and out.loc["a", "percent_orders"] == 50.0


# ---- biomarkers (Shihyun) ------------------------------------------------------------------------
def test_placeholder_hormone_values_are_dropped_and_range_flags_set():
    raw = pd.DataFrame({"customer_id": list("abc"), "sample_id": list("xyz"), "hormone": ["FSH"] * 3,
                        "value": [-1.0, 5.0, float("inf")], "ref_low": [3.0] * 3, "ref_high": [10.0] * 3,
                        "created_date": pd.Timestamp("2024-01-01")})
    clean = bio_clean.clean_hormones(raw)
    assert clean["value"].tolist() == [5.0] and not clean["below_range"].any()


def test_switch_matrix_counts_first_vs_last():
    rx = pd.DataFrame({"customer_id": ["a", "a", "b"], "sku": ["AD-BC-DAYSEE00", "AD-BC-SLYND000", "AD-BC-DAYSEE00"],
                       "date_order_placed": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-01-05"])})
    patients = bio_clean.rx_per_patient(rx)
    m = bio_analysis.switch_matrix(patients)
    assert m.loc["combined pill", "progestin-only pill"] == 1 and m.loc["combined pill", "combined pill"] == 1


# ---- funnel (Michelle) ---------------------------------------------------------------------------
def test_bulk_accounts_are_split_from_customers():
    cols = funnel_clean.CUSTOMER_COLUMNS
    d = pd.DataFrame({c: [None, None] for c in cols})
    d["n_orders"] = [1, 12]
    d["result_approved"] = [False, False]
    customers, bulk = funnel_clean.prepare_customers(d)
    assert len(customers) == 1 and len(bulk) == 1


def test_missing_customer_columns_are_named():
    with pytest.raises(ValueError, match="Required columns missing"):
        funnel_clean.prepare_customers(pd.DataFrame({"customer_id": [1]}))
