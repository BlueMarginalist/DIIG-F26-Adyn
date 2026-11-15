"""Virtual care and repeat visits. Analyses by Susan Li (susan-virtual-care branch).

The tested logic lives in lib/virtual_care (Susan's VirtualCareEDA, unchanged). This class only asks
for the right data, reshapes each result into a tidy long table and attaches the chart spec.
"""
from __future__ import annotations

from functools import cached_property

import numpy as np
import pandas as pd

from ..lib.virtual_care.analysis import VirtualCareEDA
from ..lib.virtual_care import clean as vc_clean
from ..module import AnalysisModule, chart
from ..source import Source

APPOINTMENT_COLUMNS = ("id", "customer_id", "appointment_date", "created_date", "status",
                       "appointment_outcome", "sku", "patient_interaction_satisfaction")
REPORT_COLUMNS = ("report_id", "customer_id", "customer_viewed_date")

TYPES = tuple(vc_clean.VISIT_TYPES)


def _long(table: pd.DataFrame, row: str, column: str, value: str) -> pd.DataFrame:
    """Crosstab (index x columns) to a long table."""
    return table.rename_axis(index=row, columns=column).stack().rename(value).reset_index()


class VirtualCare(AnalysisModule):
    name = "virtual_care"
    title = "Virtual care and repeat visits"
    owner = "Susan Li"
    sources = (
        Source("virtual_care", "appointments", APPOINTMENT_COLUMNS),
        Source("virtual_care", "reports", REPORT_COLUMNS),
        Source("virtual_care", "repeat_summary", ("factor", "category", "customers", "repeat_customers", "cutoff_exclusive", "window_days")),
        Source("virtual_care", "customer_cohort", ("customer_id", "por_approved", "first_viewed_date")),
    )
    assumptions = (
        "Only completed visits are counted for visit totals, gaps, transitions and satisfaction.",
        "Appointment timestamps are assumed to be UTC; confirm the source time zone.",
        "Reports are matched to appointments by customer only, so one appointment can serve several reports.",
        "Refill and yearly-visit patterns are unconfirmed.",
        "Repeat-visit charts are exploratory, unadjusted associations; no causal or validated prediction claims.",
        "Repeat cutoff completeness is unconfirmed. The first observed visit may not be first-ever; test accounts remain included.",
        "Rx order creation timestamps are assumed UTC; order presence does not establish medication use.",
        "Provider labels are temporary groups, not verified NPIs or performance rankings.",
    )

    @cached_property
    def eda(self) -> VirtualCareEDA:
        return VirtualCareEDA(self.data("appointments"), self.data("reports"))

    @cached_property
    def repeat_table(self):
        table = self.data("repeat_summary").copy()
        if table.empty and self.cfg.vc_data_through:
            table = pd.DataFrame([dict(factor=factor, category="No eligible customers", customers=0,
                                      repeat_customers=0, cutoff_exclusive=self.cfg.params()["vc_cutoff"],
                                      window_days=self.cfg.vc_window_days)
                                  for factor in ("overall", "age", "rx", "provider")])
        if table.empty or table.cutoff_exclusive.isna().any():
            raise ValueError("Supply --vc-data-through YYYY-MM-DD for live repeat charts; cutoff is provisional")
        for col in ("customers", "repeat_customers"):
            table[col] = pd.to_numeric(table[col], errors="raise")
        if not np.isfinite(table[["customers", "repeat_customers"]].to_numpy()).all():
            raise ValueError("Repeat counts must be finite")
        if (table[["customers", "repeat_customers"]] % 1 != 0).any().any():
            raise ValueError("Repeat counts must be whole numbers")
        if table.cutoff_exclusive.nunique() != 1 or table.window_days.nunique() != 1:
            raise ValueError("Repeat summary settings disagree")
        if ((table.repeat_customers < 0) | (table.repeat_customers > table.customers) |
                (table.customers < 0)).any():
            raise ValueError("Invalid repeat summary counts")
        totals = table.groupby("factor")[["customers", "repeat_customers"]].sum()
        if set(totals.index) != {"overall", "age", "rx", "provider"} or (totals.nunique() > 1).any():
            raise ValueError("Repeat summary factor totals disagree")
        table["percent"] = 100 * table.repeat_customers / table.customers.replace(0, np.nan)
        table["small_group"] = table.customers < self.cfg.vc_small_group
        table["cutoff_completeness_confirmed"] = False
        mask = table.factor.eq("provider") & ~table.category.isin(["Missing provider", "Tied first visits"])
        keys = sorted(table.loc[mask, "category"].unique())
        labels = {key: f"Provider {i+1}" for i, key in enumerate(keys)}
        table.loc[mask, "category"] = table.loc[mask, "category"].map(labels)
        return table

    def _repeat_factor(self, factor):
        return self.repeat_table.loc[self.repeat_table.factor.eq(factor)].drop(columns="factor").copy()

    @chart("Observed repeat visits within the configured window", "bar", x="category", y="percent",
           note="Among customers whose first observed completed visit permits the full window before the provisional cutoff. Strictly later visits count. See exported cutoff and window_days; completeness is unconfirmed.")
    def repeat_overall(self):
        return self._repeat_factor("overall")

    @chart("Observed repeat visits by age at first observed visit", "bar", x="category", y="percent",
           x_order=("Under 18", "18-29", "30-39", "40+", "Unknown or invalid"),
           note="Unadjusted descriptive rates; small_group flags limited denominators. Unknown or invalid ages remain separate. Cutoff completeness is unconfirmed.")
    def repeat_by_age(self):
        return self._repeat_factor("age")

    @chart("Observed repeat visits by prior recorded Rx order", "bar", x="category", y="percent",
           note="Any Rx order created by the first observed visit; not medication use. Missing order timestamps remain Unknown when no prior dated order is known. Naive creation times assumed UTC. Cutoff is provisional.")
    def repeat_by_rx(self):
        return self._repeat_factor("rx")

    @chart("Observed repeat visits by first-visit provider group", "table", internal=True,
           note="Internal review only: sparse, unadjusted groups cannot support provider rankings. Temporary labels are not NPIs. Tied first visits and missing providers stay separate. Cutoff is provisional.")
    def repeat_by_provider(self):
        return self._repeat_factor("provider")

    @chart("First observed completed visit type", "bar", x="first_type", y="customers", internal=True,
           note="First observed dated completion is not necessarily first-ever care. Unknown types and earliest timestamp ties remain separate. Async-first is not a confirmed rule violation.")
    def first_visit_types(self):
        visits = self.eda.completed
        dated = visits.loc[visits.appointment_date.notna()].copy()
        first = dated.groupby("customer_id").appointment_date.transform("min")
        earliest = dated.loc[dated.appointment_date.eq(first)].copy()
        earliest["kind"] = np.where(earliest.visit_type.isin(vc_clean.VIDEO_TYPES), "Video", earliest.visit_type)
        groups = earliest.groupby("customer_id").kind.agg(["size", "first"])
        labels = groups["first"].where(groups["size"].eq(1), "Tied earliest visits")
        n = len(labels)
        excluded = visits.customer_id.nunique() - n
        return pd.DataFrame([dict(first_type=kind, customers=int(labels.eq(kind).sum()),
                                  denominator=n, customers_without_dated_visits=int(excluded))
                             for kind in ("Video", "Async", "Unknown", "Tied earliest visits")])

    @chart("Completed visit counts among customers with PoR-approved results", "bar",
           x="visit_group", y="percent", color="visit_type",
           x_order=("0", "1", "2", "3", "4+"), filters=("visit_type",),
           note="Unique customers with at least one PoR-approved report; lifetime observed completed visits. Each type has the same denominator. Missing type stays Unknown.")
    def approved_visit_frequency(self):
        cohort = self.data("customer_cohort")
        ids = cohort.loc[cohort.por_approved.eq(True), "customer_id"].dropna().unique()
        rows = []
        for kind in ("All visit types",) + TYPES:
            visits = self.eda.completed
            if kind != "All visit types":
                visits = visits.loc[visits.visit_type.eq(kind)]
            counts = visits.groupby("customer_id").size().reindex(ids, fill_value=0)
            groups = counts.clip(upper=4)
            for number in range(5):
                n = int(groups.eq(number).sum())
                rows.append(dict(visit_type=kind, visit_group=str(number) if number < 4 else "4+",
                                 customers=n, denominator=len(ids),
                                 percent=100*n/len(ids) if len(ids) else np.nan))
        return pd.DataFrame(rows)

    @chart("Virtual care after a customer's first report view", "bar",
           x="outcome", y="percent",
           note="Denominator: unique linked report viewers. Booking uses created_date at/after first view. Completion requires that booking plus a completed visit dated at/after view. Booked without completion is observed status, not confirmed abandonment; scheduled visits may still occur.")
    def viewer_conversion(self):
        cohort = self.data("customer_cohort").copy()
        cohort["first_viewed_date"] = pd.to_datetime(cohort.first_viewed_date, utc=True, format="mixed")
        viewers = cohort.loc[cohort.customer_id.notna() & cohort.first_viewed_date.notna(),
                             ["customer_id", "first_viewed_date"]].drop_duplicates("customer_id")
        joined = self.eda.appointments.merge(viewers, on="customer_id", how="inner")
        booked = joined.loc[joined.created_date.ge(joined.first_viewed_date)]
        completed = booked.loc[booked.status.eq(vc_clean.COMPLETED_STATUS) &
                               booked.appointment_outcome.eq(vc_clean.COMPLETED_OUTCOME) &
                               booked.appointment_date.ge(booked.first_viewed_date)]
        b, c = set(booked.customer_id), set(completed.customer_id)
        n = len(viewers)
        missing_created = joined.loc[joined.created_date.isna(), "customer_id"].nunique()
        rows = []
        for label, count in [("Booked", len(b)), ("Completed", len(c)),
                             ("Booked without observed completion", len(b-c))]:
            rows.append(dict(outcome=label, customers=count, denominator=n,
                             percent=100*count/n if n else np.nan,
                             viewers_with_missing_booking_dates=int(missing_created)))
        return pd.DataFrame(rows)

    @chart("Completed visits per customer, by visit type", "bar", x="visit_group", y="customer_ids",
           color="visit_type", x_order=("1", "2", "3–5", "6+"), filters=("visit_type",),
           note="Customers can appear under several visit types. Unknown types stay visible.")
    def visit_frequency(self):
        out = self.eda.visit_frequency()
        out["visit_group"] = out["visit_group"].astype(str)
        return out

    @chart("Typical time covered by repeat visits", "bar", x="visit_type", y="median_span_days",
           x_order=TYPES,
           note="Needs two dated visits of the same type. A span is not total time enrolled.")
    def visit_spans(self):
        return self.eda.visit_summary()[["visit_type", "customer_ids", "repeat_customer_ids",
                                         "ids_with_usable_span", "median_span_days"]]

    @chart("Time from first to last completed visit, across all types", "bar",
           x="visit_scope", y="median_span_days",
           note="Includes all completed visit types, including Unknown. Needs two dated visits; not time enrolled.")
    def overall_visit_span(self):
        visits = self.eda.completed
        spans = visits.groupby("customer_id").appointment_date.agg(["count", "min", "max"])
        eligible = spans.loc[spans["count"].ge(2)]
        days = (eligible["max"] - eligible["min"]).dt.total_seconds() / 86400
        return pd.DataFrame([{
            "visit_scope": "All visit types",
            "customers_with_completed_visits": len(spans),
            "customers_with_usable_span": len(days),
            "customers_without_usable_span": len(spans) - len(days),
            "median_span_days": days.median(),
        }])

    @chart("Days between a customer's visits", "bar", x="visit_type", y="median_days", color="interval",
           x_order=TYPES, filters=("interval",),
           note="Gaps are within one visit type; zero-day gaps are kept.")
    def visit_gaps(self):
        g = self.eda.gap_summary()
        first = g.rename(columns={"ids_with_first_gap": "customers", "median_first_gap_days": "median_days"})
        second = g.rename(columns={"ids_with_second_gap": "customers", "median_second_gap_days": "median_days"})
        cols = ["visit_type", "customers", "median_days"]
        return pd.concat([first[cols].assign(interval="1st to 2nd visit"),
                          second[cols].assign(interval="2nd to 3rd visit")], ignore_index=True)

    @chart("How soon after viewing a report customers book", "bar", x="wait_group", y="reports",
           color="booking_type", stack=True, x_order=tuple(vc_clean.WAIT_GROUPS),
           filters=("booking_type",),
           note="All appointment statuses included. A timing proxy per report, not first-ever booking.")
    def report_waits(self):
        return _long(self.eda.report_wait_counts(), "wait_group", "booking_type", "reports")

    @chart("Median days from report view to booking, by visit type", "bar", x="visit_type",
           y="median_wait_days", x_order=TYPES)
    def report_wait_by_type(self):
        return self.eda.report_type_summary()

    @chart("Which visit type follows which", "heatmap", x="next_type", y="visit_type", color="pairs",
           note="Counts are pairs of consecutive visits, not people. Pairs touching tied timestamps are excluded.")
    def transitions(self):
        return _long(self.eda.transition_table(), "visit_type", "next_type", "pairs")

    @chart("Days from a video visit to the next async visit", "bar", x="preceding_video_type",
           y="median_gap_days", note="Each async visit is matched to the latest earlier known video visit.")
    def video_to_async(self):
        return self.eda.async_summary()

    @chart("Physician-reported score availability", "bar", x="visit_type", y="visits",
           color="score_status", stack=True, x_order=TYPES,
           note="Scores are reported by physicians, not customers. Describes availability, not score level. Async blanks are not expected.")
    def satisfaction(self):
        return _long(self.eda.satisfaction_availability(), "visit_type", "score_status", "visits")

    @chart("Completed visits per month", "line", x="month", y="visits", color="visit_type",
           filters=("visit_type",), note="The May 2024 spike is likely launch testing (client feedback).")
    def monthly_visits(self):
        return self.eda.monthly_visits()

    @chart("Data-quality checks", "table", internal=True,
           note="Review before interpreting any virtual-care result.")
    def quality(self):
        q = self.eda.quality_summary().iloc[0]
        return pd.DataFrame({"check": q.index, "value": q.to_numpy()})

    @classmethod
    def demo_sources(cls, cfg):
        """Synthetic appointments and viewed reports (seeded, no real patients)."""
        rng = np.random.default_rng(11)
        skus = ["VC-SYNC-15CHRG", "VC-SYNC-25CHRG", "VC-ASYC-ADCHRG", "VC-ASYC-ADFREE"]
        start = pd.Timestamp("2024-01-01", tz="UTC")
        rows = []
        for c in range(180):
            n = 1 + int(rng.geometric(0.45)) - 1
            first = int(rng.integers(0, 330))
            for k in range(n):
                day = first + int(k * rng.integers(5, 60))
                sku = skus[int(rng.integers(0, 4))] if rng.random() > 0.04 else None
                done = rng.random() < 0.88
                video = sku in skus[:2]
                score = float(rng.integers(5, 11)) if (done and video and rng.random() < 0.7) else None
                rows.append(dict(
                    id=len(rows) + 1, customer_id=f"demo-{c:03d}",
                    appointment_date=start + pd.Timedelta(days=day, hours=int(rng.integers(8, 18))),
                    created_date=start + pd.Timedelta(days=max(day - int(rng.integers(1, 14)), 0)),
                    status="completed" if done else str(rng.choice(["scheduled", "cancelled"])),
                    appointment_outcome="visit complete" if done else None,
                    sku=sku, patient_interaction_satisfaction=score))
        appointments = pd.DataFrame(rows)
        reports = pd.DataFrame({
            "report_id": np.arange(1, 241),
            "customer_id": [None if i % 80 == 0 else f"demo-{int(rng.integers(0, 180)):03d}" for i in range(240)],
            "customer_viewed_date": [(start + pd.Timedelta(days=int(rng.integers(0, 330)))).isoformat()
                                     for _ in range(240)]})
        cohort = pd.DataFrame({"customer_id": [f"demo-{c:03d}" for c in range(190)],
                               "por_approved": [c % 5 != 0 for c in range(190)]})
        viewed = reports.groupby("customer_id").customer_viewed_date.min()
        cohort["first_viewed_date"] = cohort.customer_id.map(viewed)
        # Synthetic aggregate source exercises the chart contract, not the live SQL.
        cutoff = cfg.params()["vc_cutoff"] or pd.Timestamp("2025-12-31", tz="UTC")
        repeat = pd.DataFrame([
            ("overall", "All eligible customers", 10, 4),
            ("age", "18-29", 6, 3), ("age", "30-39", 3, 1),
            ("age", "Unknown or invalid", 1, 0),
            ("rx", "Rx order recorded by first visit", 4, 1),
            ("rx", "No Rx order recorded by first visit", 5, 3),
            ("rx", "Unknown Rx timing", 1, 0),
            ("provider", "demo-provider-a", 7, 3),
            ("provider", "Missing provider", 2, 1),
            ("provider", "Tied first visits", 1, 0),
        ], columns=["factor", "category", "customers", "repeat_customers"])
        repeat["cutoff_exclusive"] = cutoff
        repeat["window_days"] = cfg.vc_window_days
        return {"appointments": appointments, "reports": reports, "customer_cohort": cohort,
                "repeat_summary": repeat}
