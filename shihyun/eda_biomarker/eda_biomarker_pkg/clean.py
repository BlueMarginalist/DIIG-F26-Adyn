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
