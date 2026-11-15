"""Cleaning and reshaping. Every function takes DataFrames and returns a new one."""
import numpy as np
import pandas as pd

# Product names and method types, inferred from the sku codes. Confirm with the team.
PRODUCTS = {
    "AD-BC-DAYSEE00": ("Daysee", "combined pill"),
    "AD-BC-JUNE20FE": ("Junel Fe", "combined pill"),
    "AD-BC-FALMIN20": ("Falmina", "combined pill"),
    "AD-BC-ALTAVE00": ("Altavera", "combined pill"),
    "AD-BC-DROS03LE": ("Drospirenone/EE", "combined pill"),
    "AD-BC-NEXT3142": ("Nextstellis", "combined pill"),
    "AD-BC-SLYND000": ("Slynd", "progestin-only pill"),
    "AD-BC-DEPOTP00": ("Depo-Provera", "injection"),
    "AD-BC-XULANE00": ("Xulane", "patch"),
    "AD-BC-NUVARI00": ("NuvaRing", "ring"),
}
# Methods that contain estrogen (relevant for clotting risk)
ESTROGEN_TYPES = {"combined pill", "patch", "ring"}

# Hormone formulation of each method type: estrogen + progestin (combined) vs progestin only
FORMULATIONS = {
    "combined pill": "estrogen + progestin",
    "patch": "estrogen + progestin",
    "ring": "estrogen + progestin",
    "progestin-only pill": "progestin only",
    "injection": "progestin only",
}
OFF_BC = "off birth control"
BC_STATUSES = [OFF_BC, "estrogen + progestin", "progestin only"]

# Age bands (years) for hormone-by-age summaries: [18, 25) -> "18-24", ..., 40+
AGE_BINS = [18, 25, 30, 35, 40, 120]
AGE_LABELS = ["18-24", "25-29", "30-34", "35-39", "40+"]

def clean_answers(answers):
    """Normalize apostrophes and treat '***' / empty strings as missing."""
    df = answers.replace({"’": "'"}, regex=True)
    return df.replace({"***": np.nan, "": np.nan})

def clean_hormones(raw):
    """Drop placeholder values (negative or infinite) and flag out-of-range results."""
    df = raw[(raw["value"] >= 0) & np.isfinite(raw["value"])].copy()
    df["below_range"] = df["value"] < df["ref_low"]
    df["above_range"] = df["value"] > df["ref_high"]
    return df


def hormone_wide(hormones):
    """One row per patient, one column per hormone (repeat tests averaged)."""
    return hormones.groupby(["customer_id", "hormone"])["value"].mean().unstack()


def label_products(rx):
    """Add product name, method type and an estrogen flag to rx orders."""
    df = rx.copy()
    df["product"] = df["sku"].map(lambda s: PRODUCTS.get(s, (s, "unknown"))[0])
    df["method_type"] = df["sku"].map(lambda s: PRODUCTS.get(s, (s, "unknown"))[1])
    df["has_estrogen"] = df["method_type"].isin(ESTROGEN_TYPES)
    df["formulation"] = df["method_type"].map(FORMULATIONS)
    return df


def rx_per_patient(rx):
    """One row per patient who ordered: products tried, first/last product and type."""
    df = label_products(rx).sort_values(["customer_id", "date_order_placed"])
    g = df.groupby("customer_id")
    out = pd.DataFrame({
        "n_rx_tried": g["sku"].nunique(),
        "n_types_tried": g["method_type"].nunique(),
        "first_product": g["product"].first(),
        "first_type": g["method_type"].first(),
        "last_product": g["product"].last(),
        "last_type": g["method_type"].last(),
        "first_order": g["date_order_placed"].min(),
        "ever_estrogen": g["has_estrogen"].any(),
    })
    out["switched"] = out["n_rx_tried"] > 1
    return out


def genetics_flags(genetics):
    """Index by patient and add a clotting-variant carrier flag."""
    df = genetics.set_index("customer_id").copy()
    df["clot_carrier"] = (df["f5_leiden"] > 0) | (df["f2_prothrombin"] > 0)
    return df


def patient_table(hormones_wide, rx_patients, genetics=None):
    """One row per patient with hormone results, joined to prescriptions and genetics."""
    df = hormones_wide.join(rx_patients, how="left")
    df["n_rx_tried"] = df["n_rx_tried"].fillna(0).astype(int)
    df["any_rx"] = df["n_rx_tried"] > 0
    df["switched"] = df["switched"].fillna(False).astype(bool)
    if genetics is not None:
        df = df.join(genetics, how="left")
    return df


def thirds(series, labels=("low", "middle", "high")):
    """Split a numeric column into thirds (tertiles)."""
    return pd.qcut(series, 3, labels=list(labels))


def split_multiselect(answers, field):
    """One yes/no column per option for a multi-select answer stored like "['A', 'B']"."""
    import ast

    def parse(v):
        if not isinstance(v, str):
            return []
        try:
            out = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return [v]
        return list(out) if isinstance(out, (list, tuple)) else [str(out)]

    lists = answers[field].map(parse)
    answered = lists.map(len) > 0
    dummies = lists[answered].explode().str.replace("’", "'").pipe(pd.get_dummies).groupby(level=0).max()
    return dummies.astype(bool)


def age_bands(age, bins=AGE_BINS, labels=AGE_LABELS):
    """Age in years -> ordered age band (e.g. '25-29')."""
    return pd.cut(age, bins=bins, labels=labels, right=False)


def hormone_age_bc(hormones, rx_orders, dob, window_days=120):
    """One row per patient, hormone and birth control status at the time of the test.

    For each blood sample, the patient counts as ON birth control if their latest
    Adyn prescription order before the test date was placed within `window_days`
    (default 120, about a 3-month supply plus a margin; confirm with the team),
    and the formulation is that order's (estrogen + progestin, or progestin only).
    Otherwise the sample counts as OFF. Repeat samples with the same status are
    averaged, so a patient tested both on and off appears once in each group.

    Only Adyn prescriptions are visible here, so a patient on a method from an
    outside provider is counted as off.
    """
    h = hormones.copy()
    h["test_date"] = pd.to_datetime(h["created_date"]).dt.tz_localize(None).dt.normalize()
    # A sample's test date is its earliest result date
    h["test_date"] = h.groupby(["customer_id", "sample_id"])["test_date"].transform("min")

    samples = h[["customer_id", "sample_id", "test_date"]].drop_duplicates().sort_values("test_date")
    rx = label_products(rx_orders)
    rx = rx[rx["formulation"].notna()].assign(
        order_date=pd.to_datetime(rx["date_order_placed"]).dt.tz_localize(None).dt.normalize())
    rx = rx[["customer_id", "order_date", "formulation"]].sort_values("order_date")
    s = pd.merge_asof(samples, rx, left_on="test_date", right_on="order_date",
                      by="customer_id", direction="backward", allow_exact_matches=False)
    on = s["order_date"].notna() & ((s["test_date"] - s["order_date"]).dt.days <= window_days)
    s["bc_status"] = s["formulation"].where(on, OFF_BC)

    births = dob.set_index("customer_id")["date_of_birth"]
    s["age"] = (s["test_date"] - pd.to_datetime(s["customer_id"].map(births))).dt.days / 365.25

    d = h.merge(s[["customer_id", "sample_id", "bc_status", "age"]], on=["customer_id", "sample_id"])
    d = d.dropna(subset=["age"])
    out = d.groupby(["customer_id", "hormone", "bc_status"], as_index=False).agg(
        value=("value", "mean"), age=("age", "mean"), n_samples=("sample_id", "nunique"))
    out["bc_status"] = pd.Categorical(out["bc_status"], categories=BC_STATUSES, ordered=True)
    out["age_band"] = age_bands(out["age"])
    return out
