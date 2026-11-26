"""Virtual-care analyses. Each public method returns a table, not a plot."""
import numpy as np
import pandas as pd
from . import clean


class VirtualCareEDA:
    """Reusable analyses for Susan's eight research questions.

    All appointments are used for report matching; only provisionally completed
    visits are used for counts, gaps, transitions, and satisfaction.
    """
    def __init__(self, appointments, reports=None):
        self.appointments = clean.prepare_appointments(appointments)
        self.completed = clean.completed_visits(self.appointments)
        self.reports = None if reports is None else clean.prepare_reports(reports)

    def visit_counts(self):
        """Q1–2: one row per customer/type, including single visits."""
        counts = self.completed.groupby(["customer_id", "visit_type"]).agg(
            visit_count=("id", "size"), dated_visits=("appointment_date", "count"),
            first_date=("appointment_date", "min"),
            last_date=("appointment_date", "max")).reset_index()
        counts["span_days"] = (counts.last_date - counts.first_date).dt.total_seconds() / 86400
        counts.loc[counts.dated_visits < 2, "span_days"] = np.nan
        return counts

    def visit_summary(self):
        out = self.visit_counts().groupby("visit_type").agg(
            customer_ids=("customer_id", "size"),
            completed_visits=("visit_count", "sum"),
            repeat_customer_ids=("visit_count", lambda s: s.ge(2).sum()),
            ids_with_usable_span=("span_days", "count"),
            median_span_days=("span_days", "median"))
        out = out.reindex(clean.VISIT_TYPES)
        for col in out.columns[:-1]:
            out[col] = out[col].fillna(0).astype(int)
        return out.reset_index()

    def visit_frequency(self):
        d = self.visit_counts()
        d["visit_group"] = pd.cut(d.visit_count, [0, 1, 2, 5, np.inf],
                                   labels=["1", "2", "3–5", "6+"])
        index = pd.MultiIndex.from_product(
            [clean.VISIT_TYPES, ["1", "2", "3–5", "6+"]],
            names=["visit_type", "visit_group"])
        return d.groupby(["visit_type", "visit_group"], observed=True).size().reindex(
            index, fill_value=0).rename("customer_ids").reset_index()

    def visit_gaps(self):
        """Q3–4: same-type first/second and second/third gaps. Zero gaps retained."""
        rows = []
        for (customer, kind), group in self.completed.groupby(["customer_id", "visit_type"]):
            dates = group.appointment_date.dropna().sort_values().tolist()
            rows.append({
                "customer_id": customer, "visit_type": kind,
                "first_to_second": (dates[1] - dates[0]).total_seconds() / 86400
                    if len(dates) >= 2 else np.nan,
                "second_to_third": (dates[2] - dates[1]).total_seconds() / 86400
                    if len(dates) >= 3 else np.nan,
            })
        return pd.DataFrame(rows, columns=["customer_id", "visit_type",
                                          "first_to_second", "second_to_third"])

    def gap_summary(self):
        out = self.visit_gaps().groupby("visit_type").agg(
            ids_with_first_gap=("first_to_second", "count"),
            median_first_gap_days=("first_to_second", "median"),
            ids_with_second_gap=("second_to_third", "count"),
            median_second_gap_days=("second_to_third", "median"))
        out = out.reindex(clean.VISIT_TYPES)
        for col in ["ids_with_first_gap", "ids_with_second_gap"]:
            out[col] = out[col].fillna(0).astype(int)
        return out.reset_index()

    def report_waits(self):
        """Q5: first appointment creation >= report view, one row per report.

        No completion-status filter. ID breaks timestamp ties deterministically;
        first_time_ties flags ambiguous first appointment types. Customer-only
        matching is provisional and may reuse an appointment across reports.
        """
        if self.reports is None:
            raise ValueError("Provide reports to run report_waits().")
        appointments = self.appointments.dropna(subset=["customer_id", "created_date"])
        rows = []
        for report in self.reports.to_dict("records"):
            row = dict(report, appointment_id=None, visit_type=None,
                       days_to_booking=np.nan, first_time_ties=0)
            candidates = appointments.loc[
                appointments.customer_id.eq(report["customer_id"]) &
                appointments.created_date.ge(report["customer_viewed_date"])
            ].sort_values(["created_date", "id"])
            if pd.notna(report["customer_id"]) and not candidates.empty:
                first = candidates.iloc[0]
                row.update(appointment_id=first.id, visit_type=first.visit_type,
                           days_to_booking=(first.created_date - report["customer_viewed_date"]).total_seconds()/86400,
                           first_time_ties=int(candidates.created_date.eq(first.created_date).sum()))
            rows.append(row)
        out = pd.DataFrame(rows, columns=list(self.reports.columns) + [
            "appointment_id", "visit_type", "days_to_booking", "first_time_ties"])
        out["wait_group"] = pd.cut(out.days_to_booking, [0, 1, 7, 30, np.inf],
                                   labels=clean.WAIT_GROUPS[:-1], include_lowest=True).astype(object)
        out.loc[out.days_to_booking.isna(), "wait_group"] = clean.WAIT_GROUPS[-1]
        out["booking_type"] = out.visit_type.fillna(clean.WAIT_GROUPS[-1])
        return out

    def report_summary(self):
        waits = self.report_waits()
        return pd.DataFrame([{
            "viewed_reports": len(waits),
            "with_later_booking": int(waits.days_to_booking.notna().sum()),
            "without_later_booking": int(waits.days_to_booking.isna().sum()),
            "reports_missing_customer": int(waits.customer_id.isna().sum()),
            "unique_matched_appointments": waits.appointment_id.nunique(),
            "reports_with_tied_first_time": int(waits.first_time_ties.gt(1).sum()),
        }])

    def report_type_summary(self):
        d = self.report_waits().dropna(subset=["days_to_booking"])
        out = d.groupby("visit_type").agg(reports=("report_id", "size"),
                                          median_wait_days=("days_to_booking", "median"))
        out = out.reindex(clean.VISIT_TYPES)
        out["reports"] = out.reports.fillna(0).astype(int)
        return out.reset_index()

    def report_wait_counts(self):
        d = self.report_waits()
        return pd.crosstab(d.wait_group, d.booking_type).reindex(
            index=clean.WAIT_GROUPS,
            columns=clean.VISIT_TYPES + [clean.WAIT_GROUPS[-1]], fill_value=0)

    def visit_transitions(self):
        """Q6: adjacent completed visits with unambiguous timestamps.

        Compute adjacency BEFORE filtering ties. Exclude any pair whose source
        or destination belongs to a tied customer/timestamp group. This prevents
        artificial transitions across excluded records.
        """
        d = self.completed.dropna(subset=["appointment_date"]).sort_values(
            ["customer_id", "appointment_date", "id"]).copy()
        d["tied_time"] = d.duplicated(["customer_id", "appointment_date"], keep=False)
        g = d.groupby("customer_id")
        d["next_type"] = g.visit_type.shift(-1)
        d["next_date"] = g.appointment_date.shift(-1)
        d["next_tied"] = g.tied_time.shift(-1)
        d["gap_days"] = (d.next_date - d.appointment_date).dt.total_seconds()/86400
        return d.loc[d.next_date.notna() & ~d.tied_time &
                     d.next_tied.eq(False) & d.gap_days.gt(0)].copy()

    def transition_table(self):
        d = self.visit_transitions()
        return pd.crosstab(d.visit_type, d.next_type).reindex(
            index=clean.VISIT_TYPES, columns=clean.VISIT_TYPES, fill_value=0)

    def video_to_async(self):
        """Q7: each async visit matched once to the latest earlier known video.

        Equal-time video/async pairs are excluded. Tied prior videos are resolved
        by appointment ID and flagged in video_time_ties. Refills unconfirmed.
        """
        video = self.completed.loc[self.completed.visit_type.isin(clean.VIDEO_TYPES)].dropna(
            subset=["appointment_date"])
        async_visits = self.completed.loc[self.completed.visit_type.eq("Async")].dropna(
            subset=["appointment_date"])
        rows = []
        for visit in async_visits.itertuples():
            earlier = video.loc[video.customer_id.eq(visit.customer_id) &
                                video.appointment_date.lt(visit.appointment_date)].sort_values(
                                    ["appointment_date", "id"], ascending=[False, True])
            if earlier.empty:
                continue
            first = earlier.iloc[0]
            rows.append({"customer_id": visit.customer_id, "async_id": visit.id,
                         "video_id": first.id, "preceding_video_type": first.visit_type,
                         "gap_days": (visit.appointment_date-first.appointment_date).total_seconds()/86400,
                         "video_time_ties": int(earlier.appointment_date.eq(first.appointment_date).sum())})
        return pd.DataFrame(rows, columns=["customer_id", "async_id", "video_id",
                                          "preceding_video_type", "gap_days", "video_time_ties"])

    def async_summary(self):
        return self.video_to_async().groupby("preceding_video_type").agg(
            async_visits=("async_id", "size"), customer_ids=("customer_id", "nunique"),
            median_gap_days=("gap_days", "median"), shortest_gap_days=("gap_days", "min"),
            longest_gap_days=("gap_days", "max")).reset_index()

    def satisfaction_availability(self):
        """Q8: preserve recorded scores, including zero; classify only blanks."""
        d = clean.label_satisfaction(self.completed)
        return pd.crosstab(d.visit_type, d.score_status).reindex(
            index=clean.VISIT_TYPES, columns=clean.SCORE_STATUSES, fill_value=0)

    def monthly_visits(self):
        d = self.completed.dropna(subset=["appointment_date"]).copy()
        d["month"] = d.appointment_date.dt.strftime("%Y-%m")
        return d.groupby(["month", "visit_type"]).size().rename("visits").reset_index()

    def quality_summary(self):
        d = self.completed
        dated = d.dropna(subset=["appointment_date"])
        return pd.DataFrame([{
            "completed_visits": len(d), "customer_ids": d.customer_id.nunique(),
            "unknown_type_visits": int(d.visit_type.eq("Unknown").sum()),
            "missing_visit_dates": int(d.appointment_date.isna().sum()),
            "records_with_tied_customer_time": int(dated.duplicated(
                ["customer_id", "appointment_date"], keep=False).sum()),
            "excluded_missing_customer": int((self.appointments.status.eq("completed") &
                self.appointments.appointment_outcome.eq("visit complete") &
                self.appointments.customer_id.isna()).sum()),
        }])
