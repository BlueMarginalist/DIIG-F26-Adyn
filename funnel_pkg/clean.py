"""Small preparation functions. Inputs are copied, never modified in place."""
import pandas as pd

from .config import Config

DATE_COLUMNS = ["created_date", "first_paid", "sent_to_allied", "shipped", "lab_received",
                "lab_processed", "result_created", "result_approved_date", "result_viewed"]

CUSTOMER_COLUMNS = ["customer_id", "age_at_signup", "state", "gift_redeemer", "bought_gift", "n_orders",
                    "n_reserved", "result_approved"] + DATE_COLUMNS


def require_columns(data, columns):
    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(f"Required columns missing: {', '.join(sorted(missing))}")


def prepare_customers(data, cfg=None):
    """Type-convert the raw customer table and split off bulk accounts.

    Returns (customers, bulk_accounts). Accounts with cfg.bulk_account_min_orders or more orders are
    treated as bulk (not real customers) and removed from the funnel."""
    cfg = cfg or Config()
    require_columns(data, CUSTOMER_COLUMNS)
    out = data.copy()
    for col in DATE_COLUMNS:
        out[col] = pd.to_datetime(out[col])
    out["age_at_signup"] = pd.to_numeric(out["age_at_signup"], errors="coerce")
    out["n_orders"] = out["n_orders"].fillna(0).astype(int)
    out["result_approved"] = out["result_approved"].eq(True)  # missing -> False, without a dtype-downcast warning
    is_bulk = out["n_orders"] >= cfg.bulk_account_min_orders
    return out[~is_bulk].copy(), out[is_bulk].copy()


def add_groups(data, cfg=None):
    """Add paid year, state group (top states + Other), gift labels and age group."""
    cfg = cfg or Config()
    out = data.copy()
    out["paid_year"] = out["first_paid"].dt.year
    state = out["state"].where(out["state"].notna(), "unknown")
    out["state_group"] = state.where(state.isin(state.value_counts().head(cfg.top_states).index), "Other")
    out["gift_redeemer_f"] = out["gift_redeemer"].map({True: "redeemed gift code", False: "no"})
    out["gift_buyer_f"] = out["bought_gift"].map({True: "bought a gift", False: "no"})
    age = pd.cut(out["age_at_signup"], list(cfg.age_bins), labels=list(cfg.age_labels)).astype(object)
    out["age_group"] = age.where(age.notna(), "unknown")
    return out


def replacement_buckets(per_customer, top=3):
    """Collapse 'replacements per customer' into 1, 2, ..., top and 'top+1+'."""
    d = per_customer.copy()
    d["bucket"] = d["n_rep"].apply(lambda n: str(int(n)) if n <= top else f"{top + 1}+")
    order = [str(i) for i in range(1, top + 1)] + [f"{top + 1}+"]
    return d.groupby("bucket")["customers"].sum().reindex(order, fill_value=0).rename("customers").reset_index()


def reason_classes(counts):
    """Split the reason counts (total, placeholder_like, structured_real) into three classes."""
    row = counts.iloc[0]
    total, placeholder, real = int(row["total"]), int(row["placeholder_like"]), int(row["structured_real"])
    return pd.DataFrame({
        "reason_class": ["placeholder / test text", "structured (lab, mail, customer)", "other / unclear"],
        "records": [placeholder, real, total - placeholder - real],
    })


def add_share(data, numerator, denominator, name):
    out = data.copy()
    out[name] = (100 * out[numerator] / out[denominator]).round(1)
    return out


def date_quality_shares(data):
    """Add share_on_busiest_day (percent) to the raw date-quality table."""
    out = data.copy()
    if "n_dates" in out:
        out["share_on_busiest_day"] = (100 * out["n_on_busiest_day"] / out["n_dates"].where(out["n_dates"] > 0)).round(1)
    return out
