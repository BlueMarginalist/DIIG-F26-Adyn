"""Test-completion funnel: fulfilment and sample return. Analyses by Michelle Zuo (michelle branch).

The tested logic lives in lib/funnel (Michelle's FunnelEDA, unchanged apart from imports). This class
hands it the cached sources, reshapes each result into a tidy table and attaches the chart spec.
Account-hygiene checks (test accounts, shared IPs, e-mail domains, staff roles) are marked internal.
"""
from __future__ import annotations

from functools import cached_property

import pandas as pd

from ..lib.funnel.analysis import FunnelEDA
from ..lib.funnel.demo import DemoData
from ..module import AnalysisModule, chart
from ..source import Source

SOURCE_NAMES = (
    "kit_outcomes", "sample_status_by_kind", "test_like_accounts", "email_domains", "shared_ips",
    "staff_roles", "paid_vs_unpaid", "order_status_totals", "replacements_per_customer",
    "replacement_reasons", "replacement_reason_counts", "replacement_totals", "replaced_sample_status",
    "replacements_by_product", "replacements_by_month", "replacement_vs_viewing", "paid_to_shipped",
    "shipped_to_lab", "lab_to_result", "result_to_approved", "return_timing", "furthest_step",
    "profile_sequence", "profile_days", "optional_forms", "steps_by_year", "medical_biography",
    "date_sanity", "date_quality", "cohort_by_month",
)
CUSTOMER_COLUMNS = ("customer_id", "created_date", "age_at_signup", "state", "gift_redeemer", "bought_gift",
                    "n_orders", "n_reserved", "first_paid", "sent_to_allied", "shipped", "lab_received",
                    "lab_processed", "result_created", "result_approved", "result_approved_date",
                    "result_viewed")
STAGES = ("Account created", "Paid order", "Sent to Allied", "Kit shipped (left Allied)",
          "Sample received by lab", "Result created", "Result approved", "Result viewed")


class _SourceView:
    """Gives FunnelEDA the attribute-style access it expects (data.kit_outcomes, ...) on top of the cache."""

    def __init__(self, module: "Funnel"):
        self._module = module

    def __getattr__(self, name):
        if name == "customers_raw" or name in SOURCE_NAMES:
            return self._module.data(name)
        raise AttributeError(name)

    def cohort_by_month(self, start, end):
        # The window is part of the query's parameters (Config.cohort_start / cohort_end).
        return self._module.data("cohort_by_month")


def _long(table: pd.DataFrame, id_cols, value_cols, names=("metric", "value")) -> pd.DataFrame:
    return table.melt(id_vars=id_cols, value_vars=value_cols, var_name=names[0], value_name=names[1])


class Funnel(AnalysisModule):
    name = "funnel"
    title = "Order-to-result funnel"
    owner = "Michelle Zuo"
    sources = (Source("funnel", "customers_raw", CUSTOMER_COLUMNS),) + tuple(
        Source("funnel", n) for n in SOURCE_NAMES)
    assumptions = (
        "Replacement orders and bulk accounts (10 or more orders) are excluded from the funnel.",
        "Timing is measured only for orders paid on or after the configured start date; older staging "
        "dates were stamped in bulk.",
        "A date column where most values fall on one day is not trustworthy for timing.",
        "Groups below the small-n threshold are flagged and should be read as noise.",
    )

    @cached_property
    def eda(self) -> FunnelEDA:
        return FunnelEDA(_SourceView(self), self.cfg)

    # ---- customer funnel -------------------------------------------------------------------
    @chart("Where paying customers drop off", "bar", x="stage", y="customers", x_order=STAGES,
           note="Unique customers reaching each stage, using real dates only.")
    def funnel(self):
        return self.eda.funnel()

    @chart("Days between stages", "range", x="step", y="p25", y2="p75",
           note="Range is the middle half (25th to 75th percentile). pct_negative above 0 means two "
                "dates disagree about the order of events.")
    def stage_gaps(self):
        d = self.eda.stage_gaps()
        d.insert(0, "step", d["from"] + " to " + d["to"])
        return d.drop(columns=["from", "to"])

    @chart("Share of paying customers who shipped, by year paid", "bar", x="group", y="pct_shipped",
           note="Small groups are flagged small_n.")
    def ship_rate_by_year(self):
        d = self.eda.ship_rates()["paid_year"]
        d["group"] = d["group"].astype(str)
        return d

    @chart("Share of paying customers who shipped, by state", "bar", x="group", y="pct_shipped",
           note="Top states by customer count; the rest are grouped as Other.")
    def ship_rate_by_state(self):
        return self.eda.ship_rates()["state"]

    @chart("After shipping: results, approvals and views, by year paid", "bar", x="group", y="value",
           color="metric", filters=("metric",), note="Percent of shipped customers.")
    def result_rates_by_year(self):
        d = self.eda.result_rates()["paid_year"]
        d["group"] = d["group"].astype(str)
        return _long(d, ["group", "shipped", "small_n"], ["pct_result", "pct_approved", "pct_viewed"])

    @chart("Funnel steps by year paid", "bar", x="yr", y="value", color="metric", filters=("metric",),
           note="Percent of paid orders that reached each step.")
    def steps_by_year(self):
        d = self.eda.steps_by_year()
        d["yr"] = d["yr"].astype(str)
        return _long(d, ["yr", "paid"], ["pct_profile", "pct_physician", "pct_shipped"])

    @chart("Where paid orders get stuck", "bar", x="furthest_step", y="orders",
           note="Furthest step each paid order reached.")
    def furthest_step(self):
        return self.eda.furthest_step()

    @chart("Paid orders by month, with profile and shipping rates", "line", x="paid_month", y="value",
           color="metric", filters=("metric",),
           note="Months far above the median with a low shipped share look like bulk or test batches.")
    def cohort_by_month(self):
        d = self.eda.cohort_by_month(self.cfg.cohort_start, self.cfg.cohort_end)
        return _long(d, ["paid_month", "paid"], ["pct_profile", "pct_shipped"])

    # ---- timing ---------------------------------------------------------------------------------
    @chart("Days per step from payment to result approval", "range", x="step", y="p25", y2="p75",
           note="Range is the 25th to 75th percentile; p50 and p90 are in the table.")
    def timing_steps(self):
        return self.eda.timing_steps()

    # ---- samples and replacements ----------------------------------------------------------------
    @chart("Saliva and blood samples: how many were valid", "bar", x="sample", y="pct_valid", color="kit",
           note="Original kits compared with replacement kits.")
    def kit_outcomes(self):
        d = self.eda.kit_outcomes()
        d["kit"] = d["is_replacement"].map({True: "replacement", False: "original"})
        rows = []
        for sample in ("saliva", "blood"):
            part = d[["kit", "shipments", f"has_{sample}", f"{sample}_valid"]].copy()
            part.columns = ["kit", "shipments", "with_sample", "valid"]
            part.insert(1, "sample", sample)
            rows.append(part)
        out = pd.concat(rows, ignore_index=True)
        out["pct_valid"] = (100 * out["valid"] / out["with_sample"].where(out["with_sample"] > 0)).round(1)
        return out

    @chart("Customers by number of replacement kits", "bar", x="bucket", y="customers")
    def replacement_buckets(self):
        return self.eda.replacement_buckets()

    @chart("Replacement kits by month", "line", x="paid_month", y="n")
    def replacements_by_month(self):
        return self.eda.replacements_by_month()

    @chart("Why kits were replaced", "bar", x="reason_class", y="records",
           note="Most free-text reasons in staging are placeholder text.")
    def replacement_reason_classes(self):
        return self.eda.replacement_reason_classes()

    @chart("Condition of the samples that were replaced", "bar", x="kind", y="n", color="status",
           stack=True)
    def replaced_sample_status(self):
        return self.eda.replaced_sample_status()

    @chart("Result viewing, with and without a replacement kit", "bar", x="needed_replacement",
           y="pct_viewed")
    def replacement_vs_viewing(self):
        return self.eda.replacement_vs_viewing()

    # ---- internal data-quality checks ------------------------------------------------------------
    @chart("Which date columns are bulk-stamped", "bar", x="column_name", y="share_on_busiest_day",
           internal=True, note="A high share on one day means the column cannot describe real timing.")
    def date_quality(self):
        return self.eda.date_quality()

    @chart("Do the dates agree about order?", "table", internal=True)
    def date_sanity(self):
        return self.eda.date_sanity()

    @chart("Test-like accounts", "table", internal=True)
    def test_like_accounts(self):
        return self.eda.test_like_accounts()

    @chart("Orders on shared IP addresses", "table", internal=True)
    def shared_ip_summary(self):
        return self.eda.shared_ip_summary()

    @chart("E-mail domains with many buyers", "table", internal=True)
    def email_domains(self):
        return self.eda.email_domains()

    @chart("Staff and provider accounts with orders", "table", internal=True)
    def staff_roles(self):
        return self.eda.staff_roles()

    @classmethod
    def demo_sources(cls, cfg):
        """Synthetic tables from Michelle's DemoData, one per source."""
        demo = DemoData(cfg=cfg)
        tables = {n: getattr(demo, n) for n in SOURCE_NAMES if n != "cohort_by_month"}
        tables["customers_raw"] = demo.customers_raw
        tables["cohort_by_month"] = demo.cohort_by_month(cfg.cohort_start, cfg.cohort_end)
        return tables
