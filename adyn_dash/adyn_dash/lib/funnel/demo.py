"""Synthetic data with the same attributes as FunnelData, for demos, tests and offline charts.

Nothing here is real. Numbers are random (seeded) and only meant to exercise the code and the charts.
"""
import numpy as np
import pandas as pd

from ...config import Config


class DemoData:
    """Drop-in replacement for FunnelData: `FunnelEDA(DemoData())` works without a database."""

    def __init__(self, n=900, seed=7, cfg=None):
        self.cfg = cfg or Config()
        self.rng = np.random.default_rng(seed)
        self.n = n
        self._build()

    # ---- helpers -----------------------------------------------------------------------------
    def refresh(self):
        pass

    def cohort_by_month(self, start="2023-01-01", end="2024-01-01"):
        d = self._cohort
        keep = (pd.to_datetime(d["paid_month"]) >= pd.Timestamp(start)) & (pd.to_datetime(d["paid_month"]) < pd.Timestamp(end))
        return d[keep].reset_index(drop=True)

    def run_diagnostics(self, group="diagnostics"):
        return {}

    # ---- build ---------------------------------------------------------------------------------------
    def _build(self):
        r, n = self.rng, self.n
        # paid dates: steady trickle plus two bursts (Feb and Jul 2023), like the staging data
        months = pd.date_range("2022-01-01", "2024-06-01", freq="MS")
        weights = np.ones(len(months))
        weights[list(months).index(pd.Timestamp("2023-02-01"))] = 8
        weights[list(months).index(pd.Timestamp("2023-07-01"))] = 7
        m = r.choice(len(months), size=n, p=weights / weights.sum())
        created = months[m] + pd.to_timedelta(r.integers(0, 27, n), unit="D")
        paid = created + pd.to_timedelta(r.integers(0, 5, n), unit="D")
        is_burst = np.isin(m, [list(months).index(pd.Timestamp("2023-02-01")), list(months).index(pd.Timestamp("2023-07-01"))])
        shipped_p = np.where(is_burst, 0.07, 0.35)
        shipped = r.random(n) < shipped_p
        sent = shipped | (r.random(n) < 0.05)
        lab = shipped & (r.random(n) < 0.85)
        res = lab & (r.random(n) < 0.8)
        appr = res & (r.random(n) < 0.85)
        viewed = appr & (r.random(n) < 0.8)

        def when(flag, base, lo, hi):
            return pd.Series(np.where(flag, base + pd.to_timedelta(r.integers(lo, hi, n), unit="D"), pd.NaT), dtype="datetime64[ns]")

        sent_d = when(sent, paid, 1, 4)
        ship_d = when(shipped, paid, 2, 14)
        states = r.choice(["CA", "TX", "NY", "FL", "NC", "WA", "IL", "OH", "PA", "GA", "AZ"], n)
        self.customers_raw = pd.DataFrame({
            "customer_id": np.arange(1, n + 1), "created_date": created, "age_at_signup": r.integers(19, 45, n),
            "state": states, "gift_redeemer": r.random(n) < 0.04, "bought_gift": r.random(n) < 0.03,
            "n_orders": np.where(r.random(n) < 0.01, 12, 1), "n_reserved": 0,
            "first_paid": paid, "sent_to_allied": sent_d, "shipped": ship_d,
            "lab_received": when(lab, ship_d, 3, 10), "lab_processed": when(lab, ship_d, 4, 12),
            "result_created": when(res, ship_d, 8, 25), "result_approved": appr,
            "result_approved_date": when(appr, ship_d, 10, 28), "result_viewed": when(viewed, ship_d, 11, 40),
        })
        self.customers_raw["n_reserved"] = (~shipped).astype(int)

        c = self.customers_raw
        total_orders = int(n * 1.05)
        self.kit_outcomes = pd.DataFrame({
            "is_replacement": [False, True], "shipments": [int(shipped.sum()), 40],
            "has_saliva": [int(shipped.sum()), 40], "saliva_valid": [int(shipped.sum() * .9), 31],
            "has_blood": [int(shipped.sum() * .98), 38], "blood_valid": [int(shipped.sum() * .8), 25]})
        self.sample_status_by_kind = pd.DataFrame({
            "kind": ["KIT-SLV", "KIT-SLV", "KIT-BLD", "KIT-BLD"], "status": ["valid", "invalid", "valid", "invalid"],
            "n": [int(shipped.sum() * .9), 40, int(shipped.sum() * .8), 70]})
        self.test_like_accounts = pd.DataFrame({"accounts": [60], "orders": [70], "reserved_orders": [65], "shipped_orders": [2]})
        self.email_domains = pd.DataFrame({
            "email_domain": ["gmail.com", "example.com", "yahoo.com", "outlook.com", "test.org"],
            "buyers": [380, 30, 60, 40, 8], "orders": [400, 55, 62, 41, 12], "reserved": [250, 55, 38, 25, 12],
            "shipped": [90, 0, 14, 9, 0]})
        self.shared_ips = pd.DataFrame({"shared_ip_groups": [6], "orders_in_groups": [80], "reserved_in_groups": [74]})
        self.staff_roles = pd.DataFrame({"role": [0, 1, 5], "accounts": [4, 2, 3], "orders": [9, 3, 5], "reserved": [8, 3, 4]})
        self.paid_vs_unpaid = pd.DataFrame({"paid": [False, False, True, True], "has_payment_issue": [False, True, False, True],
                                            "orders": [60, 12, n - 20, 20]})
        self.order_status_totals = pd.DataFrame({"non_replacement_orders": [total_orders], "reserved": [int((~shipped).sum())]})
        self.replacements_per_customer = pd.DataFrame({"n_rep": [1, 2, 3, 5], "customers": [58, 20, 8, 2]})
        self.replacement_reasons = pd.DataFrame({"reason": ["Some reason", "Lab reported insufficient saliva", "Mail: lost in transit",
                                                            "testing", "Customer reported damaged tube"], "n": [60, 14, 9, 8, 6]})
        self.replacement_reason_counts = pd.DataFrame({"total": [150], "placeholder_like": [105], "structured_real": [33]})
        self.replacement_totals = pd.DataFrame({"n_rows": [150], "distinct_old_shipments": [140], "reimbursed": [4]})
        self.replaced_sample_status = pd.DataFrame({"kind": ["KIT-BLD", "KIT-SLV", "KIT-BLD", "KIT-SLV"],
                                                    "status": ["invalid", "invalid", "valid", "valid"], "n": [70, 25, 30, 20]})
        self.replacements_by_product = pd.DataFrame({"name": ["Replacement kit"], "sku": ["REP-1"], "n": [150]})
        self.replacements_by_month = pd.DataFrame({"paid_month": pd.date_range("2023-01-01", periods=12, freq="MS"),
                                                   "n": [4, 30, 6, 5, 8, 9, 40, 12, 7, 10, 9, 10]})
        self.replacement_vs_viewing = pd.DataFrame({"needed_replacement": [False, True],
                                                    "shipped_customers": [int(shipped.sum()) - 60, 60], "viewed": [int(viewed.sum() * .93), int(viewed.sum() * .07)]})
        self.paid_to_shipped = pd.DataFrame({"n": [int(shipped.sum())], "p25": [4.0], "p50": [8.0], "p75": [20.0], "p90": [60.0], "negative": [0]})
        self.shipped_to_lab = pd.DataFrame({"n": [int(lab.sum())], "p25": [-30.0], "p50": [-5.0], "p75": [3.0], "p90": [9.0],
                                            "negative": [int(lab.sum() * .75)], "over_90_days": [0]})
        self.lab_to_result = pd.DataFrame({"n": [int(res.sum())], "p25": [1.0], "p50": [4.0], "p75": [9.0], "p90": [18.0]})
        self.result_to_approved = pd.DataFrame({"n": [int(appr.sum())], "p25": [0.0], "p50": [1.0], "p75": [2.0], "p90": [5.0]})
        self.return_timing = pd.DataFrame({"shipments": [int(shipped.sum())], "delivered_to_customer_logged": [int(shipped.sum() * .9)],
                                           "saliva_return_logged": [int(shipped.sum() * .6)], "blood_return_logged": [int(shipped.sum() * .5)],
                                           "med_days_saliva_back": [0.0], "med_days_blood_back": [0.0], "p90_days_blood_back": [0.0]})
        paid_n = n
        prof = int(paid_n * .31)
        self.furthest_step = pd.DataFrame({
            "furthest_step": ["1-2 paid, profile not complete", "3 profile complete, not approved", "4 physician approved, not shipped", "5 shipped"],
            "orders": [paid_n - prof, int(prof * .35), int(prof * .2), int(shipped.sum())]})
        self.profile_sequence = pd.DataFrame({"shipped_orders": [200], "no_profile_record": [9], "profile_before_ship": [181], "profile_after_ship": [10]})
        self.profile_days = pd.DataFrame({"n": [prof], "p25": [0.0], "p50": [1.0], "p75": [6.0], "p90": [40.0],
                                          "profile_before_payment": [int(prof * .6)], "over_30_days": [int(prof * .12)], "over_90_days": [int(prof * .05)]})
        self.optional_forms = pd.DataFrame({"shipped": [False, True], "orders": [150, 200], "intake_done": [20, 110], "medhist_done": [18, 105]})
        yr = pd.DatetimeIndex(c["first_paid"]).year
        rows = [{"yr": int(y), "paid": int((yr == y).sum()), "profile_done": int(((yr == y) & (r.random(n) < .3)).sum()),
                 "physician_ok": int(((yr == y) & (r.random(n) < .2)).sum()), "shipped": int(((yr == y) & shipped).sum())}
                for y in sorted(set(yr))]
        self.steps_by_year = pd.DataFrame(rows)
        self.medical_biography = pd.DataFrame({"completion": ["complete", "partial"], "orders": [120, 40], "shipped": [90, 10]})
        self.date_sanity = pd.DataFrame({"n": [200], "shipped_before_paid": [80], "shipped_before_created": [75],
                                         "med_paid_minus_created_days": [0.0], "med_shipped_minus_created_days": [-3.0]})
        busiest = [4, 55, 70, 62, 85, 80, 3, 5, 6, 9]
        from .constants import DATE_COLUMNS
        self.date_quality = pd.DataFrame({
            "table_name": [t for t, _ in DATE_COLUMNS], "column_name": [col for _, col in DATE_COLUMNS],
            "n_dates": [n] * len(DATE_COLUMNS), "n_on_busiest_day": [int(n * b / 100) for b in busiest],
            "distinct_days": [300] * len(DATE_COLUMNS)})
        # cohort table, derived from the synthetic customers so it agrees with the funnel
        pm = pd.to_datetime(c["first_paid"]).dt.to_period("M").dt.to_timestamp()
        co = pd.DataFrame({"paid_month": pm, "profile_done": r.random(n) < .31, "shipped": c["shipped"].notna()})
        self._cohort = co.groupby("paid_month").agg(paid=("shipped", "size"), profile_done=("profile_done", "sum"),
                                                    shipped=("shipped", "sum")).reset_index()
