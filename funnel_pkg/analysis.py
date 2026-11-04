"""Test-completion funnel analyses. Each public method returns a table, not a plot."""
from functools import cached_property

import pandas as pd

from . import clean
from .config import Config

# (from, to) pairs for days between stages (lab dates are batch-level in staging)
GAP_PAIRS = [("created_date", "first_paid"), ("first_paid", "sent_to_allied"), ("sent_to_allied", "shipped"),
             ("first_paid", "shipped"), ("shipped", "lab_received"), ("lab_processed", "result_created"),
             ("result_created", "result_approved_date"), ("result_approved_date", "result_viewed"),
             ("result_created", "result_viewed"), ("first_paid", "result_viewed")]


class FunnelEDA:
    """Reusable analyses for the test completion funnel (fulfillment and sample return).

    `data` is a FunnelData (live database) or demo.DemoData (synthetic); it only needs the same attributes.
    """

    def __init__(self, data, cfg=None):
        self.data = data
        self.cfg = cfg or Config()

    # ---- customer-level funnel -----------------------------------------------------------------
    @cached_property
    def _prepared(self):
        return clean.prepare_customers(self.data.customers_raw, self.cfg)

    @property
    def customers(self):
        return self._prepared[0]

    @property
    def bulk_accounts(self):
        return self._prepared[1]

    def funnel(self):
        """Unique customers reaching each stage (real dates only; replacements and bulk accounts excluded)."""
        df = self.customers
        stages = [
            ("Account created", df["created_date"].notna()),
            ("Paid order", df["first_paid"].notna()),
            ("Sent to Allied", df["sent_to_allied"].notna()),
            ("Kit shipped (left Allied)", df["shipped"].notna()),
            ("Sample received by lab", df["lab_received"].notna()),
            ("Result created", df["result_created"].notna()),
            ("Result approved", df["result_approved"]),
            ("Result viewed", df["result_viewed"].notna()),
        ]
        base_paid = int(stages[1][1].sum())
        rows, prev = [], None
        for name, flag in stages:
            n = int(flag.sum())
            rows.append({
                "stage": name, "customers": n,
                "pct_of_prev": round(100 * n / prev, 1) if prev else None,
                "pct_of_paid": round(100 * n / base_paid, 1) if name != "Account created" and base_paid else None,
                "lost_vs_prev": (prev - n) if prev is not None else None,
            })
            prev = n
        return pd.DataFrame(rows)

    def largest_drop(self):
        """The stage with the biggest loss versus the one before it."""
        table = self.funnel()
        row = table.loc[table["lost_vs_prev"].astype(float).idxmax()]
        return {"stage": row["stage"], "lost": int(row["lost_vs_prev"])}

    def stage_gaps(self):
        """Days between stages. pct_negative > 0 means the two dates disagree about the order."""
        df, rows = self.customers, []
        for a, b in GAP_PAIRS:
            both = df[a].notna() & df[b].notna()
            days = (df.loc[both, b] - df.loc[both, a]).dt.total_seconds() / 86400
            rows.append({
                "from": a, "to": b, "n": int(both.sum()),
                "median_days": round(days.median(), 1) if len(days) else None,
                "p25": round(days.quantile(.25), 1) if len(days) else None,
                "p75": round(days.quantile(.75), 1) if len(days) else None,
                "pct_negative": round(100 * (days < 0).mean(), 1) if len(days) else None,
            })
        return pd.DataFrame(rows)

    def ship_rates(self):
        """Paid -> shipped by paid year, state and gift status. Returns {name: table}."""
        paid = clean.add_groups(self.customers[self.customers["first_paid"].notna()], self.cfg)
        paid["shipped_f"] = paid["shipped"].notna()
        out = {}
        for col, name in [("paid_year", "paid_year"), ("state_group", "state"),
                          ("gift_redeemer_f", "gift_redeemer"), ("gift_buyer_f", "gift_buyer")]:
            g = paid.groupby(col).agg(paid_customers=("shipped_f", "size"), shipped=("shipped_f", "sum"))
            g["pct_shipped"] = (100 * g["shipped"] / g["paid_customers"]).round(1)
            g["small_n"] = g["paid_customers"] < self.cfg.small_n
            out[name] = g.reset_index().rename(columns={col: "group"})
        return out

    def result_rates(self):
        """Shipped -> result created / approved / viewed by paid year, age, state and gift status."""
        paid = clean.add_groups(self.customers[self.customers["first_paid"].notna()], self.cfg)
        sh = paid[paid["shipped"].notna()].copy()
        sh["result_f"] = sh["result_created"].notna()
        sh["viewed_f"] = sh["result_viewed"].notna()
        out = {}
        for col, name in [("paid_year", "paid_year"), ("age_group", "age"),
                          ("state_group", "state"), ("gift_redeemer_f", "gift_redeemer")]:
            g = sh.groupby(col).agg(shipped=("result_f", "size"), got_result=("result_f", "sum"),
                                    approved=("result_approved", "sum"), viewed=("viewed_f", "sum"))
            g["pct_result"] = (100 * g["got_result"] / g["shipped"]).round(1)
            g["pct_approved"] = (100 * g["approved"] / g["shipped"]).round(1)
            g["pct_viewed"] = (100 * g["viewed"] / g["shipped"]).round(1)
            g["small_n"] = g["shipped"] < self.cfg.small_n
            out[name] = g.reset_index().rename(columns={col: "group"})
        return out

    def kit_outcomes(self):
        """Per shipment: did a saliva / blood sample exist and was it valid? (original vs replacement kits)"""
        return self.data.kit_outcomes.copy()

    def sample_status(self):
        return self.data.sample_status_by_kind.copy()

    # ---- test / internal accounts ---------------------------------------------------------------
    def email_domains(self):
        return self.data.email_domains.copy()

    def shared_ip_summary(self):
        """Shared-IP orders versus all orders: share still reserved (never sent to fulfillment)."""
        s, t = self.data.shared_ips.iloc[0], self.data.order_status_totals.iloc[0]
        return pd.DataFrame({
            "group": ["All orders", "Orders on shared IPs"],
            "orders": [int(t["non_replacement_orders"]), int(s["orders_in_groups"] or 0)],
            "reserved": [int(t["reserved"]), int(s["reserved_in_groups"] or 0)],
        }).assign(pct_reserved=lambda d: (100 * d["reserved"] / d["orders"].where(d["orders"] > 0)).round(1))

    def test_like_accounts(self):
        return self.data.test_like_accounts.copy()

    def staff_roles(self):
        return self.data.staff_roles.copy()

    def paid_vs_unpaid(self):
        return self.data.paid_vs_unpaid.copy()

    # ---- replacement kits --------------------------------------------------------------------------
    def replacements_per_customer(self):
        return self.data.replacements_per_customer.copy()

    def replacement_buckets(self):
        return clean.replacement_buckets(self.data.replacements_per_customer)

    def replacement_reason_classes(self):
        return clean.reason_classes(self.data.replacement_reason_counts)

    def replacement_reasons(self):
        """Free-text reasons seen cfg.reason_min_count or more times."""
        return self.data.replacement_reasons.copy()

    def replacement_totals(self):
        return self.data.replacement_totals.copy()

    def replaced_sample_status(self):
        """Status of the ORIGINAL samples that were replaced (what failed: kind + status)."""
        return self.data.replaced_sample_status.copy()

    def replacements_by_product(self):
        return self.data.replacements_by_product.copy()

    def replacements_by_month(self):
        return self.data.replacements_by_month.copy()

    def replacement_vs_viewing(self):
        return clean.add_share(self.data.replacement_vs_viewing, "viewed", "shipped_customers", "pct_viewed")

    # ---- time between steps -------------------------------------------------------------------------
    def timing_steps(self):
        """p25/p50/p75/p90 days per step, plus how many gaps are negative (dates disagree)."""
        parts = []
        for step, name in [("paid -> shipped", "paid_to_shipped"), ("shipped -> lab received", "shipped_to_lab"),
                           ("lab received -> result created", "lab_to_result"),
                           ("result created -> approved", "result_to_approved")]:
            d = getattr(self.data, name).copy()
            d.insert(0, "step", step)
            parts.append(d)
        return pd.concat(parts, ignore_index=True)

    def return_timing(self):
        return self.data.return_timing.copy()

    # ---- blocking steps ----------------------------------------------------------------------------
    def furthest_step(self):
        return self.data.furthest_step.copy()

    def profile_sequence(self):
        """Does profile completion come before shipping?"""
        return self.data.profile_sequence.copy()

    def profile_days(self):
        """Days from payment to a complete profile."""
        return self.data.profile_days.copy()

    def optional_forms(self):
        return self.data.optional_forms.copy()

    def steps_by_year(self):
        d = self.data.steps_by_year.copy()
        for col, name in [("profile_done", "pct_profile"), ("physician_ok", "pct_physician"), ("shipped", "pct_shipped")]:
            d = clean.add_share(d, col, "paid", name)
        return d

    def medical_biography(self):
        return self.data.medical_biography.copy()

    def cohort_by_month(self, start="2023-01-01", end="2024-01-01"):
        d = self.data.cohort_by_month(start, end)
        d = clean.add_share(d, "profile_done", "paid", "pct_profile")
        return clean.add_share(d, "shipped", "paid", "pct_shipped")

    # ---- date quality -------------------------------------------------------------------------------
    def date_quality(self):
        """Which date columns are bulk-stamped? A high share on the busiest day means do not trust the column."""
        return clean.date_quality_shares(self.data.date_quality)

    def date_sanity(self):
        return self.data.date_sanity.copy()

    # ---- everything as aggregate tables (what make_plots.py exports) ---------------------------------
    def tables(self, cohort_start="2023-01-01", cohort_end="2024-01-01"):
        """All aggregate tables by name. Row-level customer data stays in memory."""
        out = {
            "funnel": self.funnel(), "stage_gaps": self.stage_gaps(), "kit_outcomes": self.kit_outcomes(),
            "sample_status": self.sample_status(), "email_domains": self.email_domains(),
            "shared_ip_summary": self.shared_ip_summary(), "test_like_accounts": self.test_like_accounts(),
            "staff_roles": self.staff_roles(), "paid_vs_unpaid": self.paid_vs_unpaid(),
            "replacements_per_customer": self.replacements_per_customer(),
            "replacement_reasons": self.replacement_reasons(),
            "replacement_reason_classes": self.replacement_reason_classes(),
            "replacement_totals": self.replacement_totals(),
            "replaced_sample_status": self.replaced_sample_status(),
            "replacements_by_product": self.replacements_by_product(),
            "replacements_by_month": self.replacements_by_month(),
            "replacement_vs_viewing": self.replacement_vs_viewing(),
            "timing_steps": self.timing_steps(), "return_timing": self.return_timing(),
            "furthest_step": self.furthest_step(), "profile_sequence": self.profile_sequence(),
            "profile_days": self.profile_days(), "optional_forms": self.optional_forms(),
            "steps_by_year": self.steps_by_year(), "medical_biography": self.medical_biography(),
            "cohort_by_month": self.cohort_by_month(cohort_start, cohort_end),
            "date_quality": self.date_quality(), "date_sanity": self.date_sanity(),
        }
        for name, table in self.ship_rates().items():
            out[f"ship_rate_by_{name}"] = table
        for name, table in self.result_rates().items():
            out[f"viewed_rate_by_{name}"] = table
        return out
