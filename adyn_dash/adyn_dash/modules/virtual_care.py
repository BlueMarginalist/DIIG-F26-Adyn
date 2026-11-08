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
    )
    assumptions = (
        "Only completed visits are counted for visit totals, gaps, transitions and satisfaction.",
        "Appointment timestamps are assumed to be UTC; confirm the source time zone.",
        "Reports are matched to appointments by customer only, so one appointment can serve several reports.",
        "Refill and yearly-visit patterns are unconfirmed.",
    )

    @cached_property
    def eda(self) -> VirtualCareEDA:
        return VirtualCareEDA(self.data("appointments"), self.data("reports"))

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

    @chart("Satisfaction scores recorded, missing or not expected", "bar", x="visit_type", y="visits",
           color="score_status", stack=True, x_order=TYPES,
           note="Describes whether a score exists, not how high it is. Async blanks are not expected.")
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
        return {"appointments": appointments, "reports": reports}
