"""Pure table-in, table-out helpers for the prescription journey.

Taken from Morgan Kay's package.ipynb. The plotting and table-loading code (load_dataframe, plot_*) was
dropped: SQL now lives in sources/prescriptions and charts are drawn by the dashboard. The functions that
compute a result are kept with their original behaviour.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
                "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def missing_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Per column: dtype, missing count/share, and unique nonmissing values."""
    return pd.DataFrame({"dtype": data.dtypes.astype(str), "n_missing": data.isna().sum(),
                         "share_missing": data.isna().mean(), "n_unique": data.nunique()}
                        ).rename_axis("column").reset_index()


def quantity_summary(data: pd.DataFrame, by: str = "bc_prescribed") -> pd.DataFrame:
    """Count and numeric summary of quantity per group; groups with missing values are retained."""
    out = data.groupby(by, dropna=False)["quantity"].agg(["count", "mean", "median", "std", "min", "max"])
    out.index = out.index.map(lambda v: "(missing)" if pd.isna(v) else str(v))
    return out.rename_axis(by).reset_index()


def monthly_counts(data: pd.DataFrame, date_col: str = "date_order_placed") -> pd.DataFrame:
    """Records per calendar month, including zero months within the date span."""
    dates = pd.to_datetime(data[date_col], errors="coerce")
    counts = dates.dt.to_period("M").value_counts().sort_index()
    if not counts.empty:
        counts = counts.reindex(pd.period_range(counts.index.min(), counts.index.max(), freq="M"), fill_value=0)
    out = counts.rename_axis("month").reset_index(name="n_records")
    out["month"] = out["month"].astype(str)
    return out


def category_counts(data: pd.DataFrame, column: str) -> pd.DataFrame:
    """Record counts per observed category; missing values get their own row."""
    counts = data[column].value_counts(dropna=False)
    labels = ["(missing)" if pd.isna(v) else str(v) for v in counts.index]
    return pd.DataFrame({column: labels, "n_records": counts.to_numpy()})


def order_status_summary(data: pd.DataFrame, status_col: str = "status") -> pd.DataFrame:
    """Count and percentage of order records in each status; blanks count as missing."""
    status = data[status_col].astype("string").str.strip().replace("", pd.NA).fillna("(missing)")
    out = status.value_counts().rename_axis("status").reset_index(name="n_orders")
    out["percent_orders"] = (out["n_orders"] / len(data) * 100).round(1) if len(data) else 0.0
    return out


FLAG_MAP = {"true": "True", "false": "False", "1": "True", "0": "False", "1.0": "True", "0.0": "False"}


def flag_counts(data: pd.DataFrame, flags: dict) -> pd.DataFrame:
    """True / False / Missing counts for approval and suspension flags."""
    rows = []
    for column, label in flags.items():
        values = data[column].astype("string").str.strip().str.lower().replace("", pd.NA)
        unknown = values.notna() & ~values.isin(FLAG_MAP.keys())
        if unknown.any():
            raise ValueError(f"Unrecognized values in {column}: {sorted(values[unknown].unique())[:5]}")
        mapped = values.map(FLAG_MAP).fillna("Missing")
        for value in ("True", "False", "Missing"):
            rows.append({"flag": label, "value": value, "n_orders": int((mapped == value).sum())})
    return pd.DataFrame(rows)


def prescriptions_per_patient(data: pd.DataFrame, patient_col: str = "patient_id") -> pd.DataFrame:
    """Prescription row count per nonmissing patient (kept in memory only)."""
    return data.groupby(patient_col).size().rename("n_prescriptions").reset_index()


def prescription_count_distribution(per_patient: pd.DataFrame) -> pd.DataFrame:
    """Number of patients for each prescription count (aggregate, safe to publish)."""
    return per_patient.groupby("n_prescriptions").size().rename("patients").reset_index()


def customer_ages(data: pd.DataFrame, as_of=None, patient_col: str = "patient_id",
                  dob_col: str = "customer_dob") -> pd.DataFrame:
    """Age per patient at as_of (today by default). Conflicting dates of birth raise an error."""
    d = data.dropna(subset=[patient_col]).copy()
    d[dob_col] = pd.to_datetime(d[dob_col], errors="coerce")
    if d.groupby(patient_col)[dob_col].nunique().gt(1).any():
        raise ValueError("Conflicting DOBs for a patient; resolve before calculating ages")
    d = d[[patient_col, dob_col]].drop_duplicates(patient_col).copy()
    date = pd.Timestamp.today().normalize() if as_of is None else pd.Timestamp(as_of).normalize()
    dob = d[dob_col]
    pending = (dob.dt.month > date.month) | ((dob.dt.month == date.month) & (dob.dt.day > date.day))
    d["age"] = (date.year - dob.dt.year - pending.astype(int)).astype("Int64")
    return d


def age_groups(ages: pd.DataFrame, width: int = 5) -> pd.DataFrame:
    """Patients per age band. Future dates of birth (negative ages) are reported as their own row."""
    age = ages["age"].dropna().astype(int)
    out = []
    negative = int((age < 0).sum())
    age = age[age >= 0]
    if not age.empty:
        low = (age // width) * width
        for start, n in low.value_counts().sort_index().items():
            out.append({"age_group": f"{start}-{start + width - 1}", "start": int(start), "patients": int(n)})
    if negative:
        out.append({"age_group": "future date of birth", "start": -1, "patients": negative})
    return pd.DataFrame(out, columns=["age_group", "start", "patients"])


def time_delays(data: pd.DataFrame, start_col: str, end_col: str, unit: str = "hours") -> pd.DataFrame:
    seconds = {"days": 86400, "hours": 3600, "minutes": 60}
    if unit not in seconds:
        raise ValueError("unit must be 'days', 'hours', or 'minutes'")
    d = data.copy()
    start = pd.to_datetime(d[start_col], errors="coerce")
    end = pd.to_datetime(d[end_col], errors="coerce")
    d[f"delay_{unit}"] = (end - start).dt.total_seconds() / seconds[unit]
    return d


def delay_histogram(data: pd.DataFrame, start_col: str, end_col: str, unit: str = "hours",
                    nonnegative: bool = False, upper_quantile=None, bins: int = 30, binwidth=None) -> pd.DataFrame:
    """Histogram of a delay. Excluded records are reported in the attrs of the returned table."""
    d = time_delays(data, start_col, end_col, unit)
    col = f"delay_{unit}"
    values = d[col]
    missing = int(values.isna().sum())
    negative = int((values < 0).sum()) if nonnegative else 0
    shown = values[values.notna() & ((values >= 0) if nonnegative else True)]
    trimmed = 0
    if upper_quantile is not None and not shown.empty:
        cutoff = shown.quantile(upper_quantile)
        trimmed = int((shown > cutoff).sum())
        shown = shown[shown <= cutoff]
    if shown.empty:
        out = pd.DataFrame(columns=["bin_start", "bin_end", "orders"])
    else:
        edges = (np.arange(np.floor(shown.min()), shown.max() + binwidth, binwidth) if binwidth else bins)
        counts, edges = np.histogram(shown, bins=edges)
        out = pd.DataFrame({"bin_start": edges[:-1].round(2), "bin_end": edges[1:].round(2), "orders": counts})
    out.attrs.update(excluded_missing=missing, excluded_negative=negative, excluded_above_cutoff=trimmed)
    return out


def value_histogram(values: pd.Series, bins: int = 20, by: pd.Series | None = None) -> pd.DataFrame:
    """Histogram with shared bin edges, optionally split by a category."""
    v = pd.to_numeric(values, errors="coerce")
    ok = v.notna()
    if not ok.any():
        return pd.DataFrame(columns=["bin_start", "bin_end", "group", "orders"])
    edges = np.histogram_bin_edges(v[ok], bins=bins)
    groups = (by.where(by.notna(), "(missing)").astype(str)[ok] if by is not None
              else pd.Series("all", index=v[ok].index))
    rows = []
    for g, part in v[ok].groupby(groups):
        counts, _ = np.histogram(part, bins=edges)
        rows += [{"bin_start": round(float(a), 2), "bin_end": round(float(b), 2), "group": g, "orders": int(n)}
                 for a, b, n in zip(edges[:-1], edges[1:], counts)]
    return pd.DataFrame(rows)


def payment_delay_summary(data: pd.DataFrame, group: str = "sku", nonnegative: bool = True) -> pd.DataFrame:
    """Payment-delay statistics per group, in days."""
    d = time_delays(data, "date_order_placed", "date_order_paid", "days")
    rows = []
    for name, g in d.groupby(group, dropna=False, observed=True):
        delays = g["delay_days"].dropna()
        negative = int(delays.lt(0).sum())
        if nonnegative:
            delays = delays[delays >= 0]
        rows.append({group: "(missing)" if pd.isna(name) else str(name), "n_orders": len(g),
                     "n_missing_delay": int(g["delay_days"].isna().sum()), "n_negative_delay": negative,
                     "n_analyzed": len(delays), "median_days": delays.median(), "mean_days": delays.mean(),
                     "p90_days": delays.quantile(0.90)})
    return pd.DataFrame(rows, columns=[group, "n_orders", "n_missing_delay", "n_negative_delay", "n_analyzed",
                                       "median_days", "mean_days", "p90_days"])


def monthly_delay_summary(data: pd.DataFrame, start_col: str, end_col: str, unit: str = "days",
                          nonnegative: bool = True) -> pd.DataFrame:
    """Monthly median and 90th-percentile delay, plus record counts (months keyed by start date)."""
    d = time_delays(data, start_col, end_col, unit)
    delay_col = f"delay_{unit}"
    d["_month"] = pd.to_datetime(d[start_col], errors="coerce").dt.to_period("M")
    columns = ["month", "n_records", "n_missing_delay", "n_negative_delay", "n_analyzed", "median", "p90"]
    d = d[d["_month"].notna()]
    if d.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for month, g in d.groupby("_month"):
        delays = g[delay_col].dropna()
        negative = int(delays.lt(0).sum())
        if nonnegative:
            delays = delays[delays >= 0]
        rows.append({"month": month, "n_records": len(g), "n_missing_delay": int(g[delay_col].isna().sum()),
                     "n_negative_delay": negative, "n_analyzed": len(delays),
                     "median": delays.median(), "p90": delays.quantile(0.90)})
    result = pd.DataFrame(rows).set_index("month")
    result = result.reindex(pd.period_range(result.index.min(), result.index.max(), freq="M")).rename_axis("month")
    count_cols = ["n_records", "n_missing_delay", "n_negative_delay", "n_analyzed"]
    result[count_cols] = result[count_cols].fillna(0).astype(int)
    out = result.reset_index()
    out["month"] = out["month"].astype(str)
    return out


def shipment_state_counts(data: pd.DataFrame, state_col: str = "state") -> pd.DataFrame:
    """Shipments per US state. Codes that are not US states are grouped as '(unrecognized)'."""
    state = data[state_col].astype("string").str.strip().str.upper().replace("", pd.NA)
    counts = state.value_counts().rename_axis("state").reset_index(name="shipments")
    counts["state"] = counts["state"].where(counts["state"].isin(US_STATES), "(unrecognized)")
    counts = counts.groupby("state", as_index=False)["shipments"].sum().sort_values("shipments", ascending=False)
    missing = int(state.isna().sum())
    if missing:
        counts = pd.concat([counts, pd.DataFrame({"state": ["(missing)"], "shipments": [missing]})], ignore_index=True)
    return counts.reset_index(drop=True)


def repeat_order_summary(rx_orders: pd.DataFrame, customer_col: str = "customer_id",
                         order_col: str = "id") -> pd.DataFrame:
    """One row per customer: distinct orders and whether they ordered again (kept in memory only)."""
    summary = (rx_orders.dropna(subset=[customer_col]).groupby(customer_col)[order_col]
               .nunique().reset_index(name="n_orders"))
    summary["repeat_customer"] = summary["n_orders"] > 1
    return summary


def repeat_customer_counts(per_customer: pd.DataFrame) -> pd.DataFrame:
    """Customers who ordered once versus more than once (aggregate)."""
    n = per_customer["repeat_customer"]
    return pd.DataFrame({"group": ["Ordered once", "Ordered again"], "customers": [int((~n).sum()), int(n.sum())]})


def check_order_shipment_links(rx_orders: pd.DataFrame, rx_shipments: pd.DataFrame) -> pd.DataFrame:
    """Check order IDs and how many shipment records each order has."""
    per_order = rx_shipments.groupby("rx_order_id").size()
    values = {
        "duplicate_order_ids": rx_orders["id"].duplicated().sum(),
        "shipments_missing_order_id": rx_shipments["rx_order_id"].isna().sum(),
        "orders_with_multiple_shipments": per_order.gt(1).sum(),
        "shipments_with_unmatched_order_id": (rx_shipments["rx_order_id"].notna()
                                               & ~rx_shipments["rx_order_id"].isin(rx_orders["id"])).sum(),
    }
    return pd.DataFrame({"check": list(values), "count": [int(v) for v in values.values()]})


def check_cost_links(rx_orders: pd.DataFrame, rx_packed: pd.DataFrame, rx_matches: pd.DataFrame) -> pd.DataFrame:
    """Check whether RxMatches can connect orders to packing/cost records."""
    links = rx_matches[["rx_order_id", "rx_packed_id"]]
    values = {
        "match_rows": len(links),
        "missing_order_id": links["rx_order_id"].isna().sum(),
        "missing_packed_id": links["rx_packed_id"].isna().sum(),
        "duplicate_link_pairs": links.duplicated().sum(),
        "orders_with_multiple_packed_ids": links.groupby("rx_order_id")["rx_packed_id"].nunique().gt(1).sum(),
        "packed_ids_linked_to_multiple_orders": links.groupby("rx_packed_id")["rx_order_id"].nunique().gt(1).sum(),
        "unmatched_order_ids": (links["rx_order_id"].notna() & ~links["rx_order_id"].isin(rx_orders["id"])).sum(),
        "unmatched_packed_ids": (links["rx_packed_id"].notna() & ~links["rx_packed_id"].isin(rx_packed["id"])).sum(),
    }
    return pd.DataFrame({"check": list(values), "count": [int(v) for v in values.values()]})
