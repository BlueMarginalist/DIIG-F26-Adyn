"""Small preparation functions. Inputs are copied, never modified in place."""
import pandas as pd

VISIT_TYPES = ["15-minute video", "25-minute video", "Async", "Unknown"]
VIDEO_TYPES = VISIT_TYPES[:2]
SKU_TYPES = {
    "VC-SYNC-15CHRG": "15-minute video",
    "VC-SYNC-25CHRG": "25-minute video",
    "VC-ASYC-ADCHRG": "Async",
    "VC-ASYC-ADFREE": "Async",
}
WAIT_GROUPS = ["Within 1 day", "Over 1–7 days", "Over 7–30 days",
               "Over 30 days", "No later booking found"]
SCORE_STATUSES = ["Recorded", "Not expected", "Missing", "Expectation unknown"]


def require_columns(data, columns):
    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(f"Required columns missing: {', '.join(sorted(missing))}")


def prepare_appointments(data):
    require_columns(data, ["id", "customer_id", "appointment_date", "created_date",
                           "status", "appointment_outcome", "sku",
                           "patient_interaction_satisfaction"])
    out = data.copy()
    if out.id.isna().any() or out.id.duplicated().any():
        raise ValueError("Appointment IDs must be present and unique.")
    for col in ["appointment_date", "created_date"]:
        # Invalid strings raise an error rather than silently disappearing.
        # Naive timestamps are assumed to be UTC. Confirm source timezone.
        out[col] = pd.to_datetime(out[col], utc=True, format="mixed")
    out["visit_type"] = out.sku.map(SKU_TYPES).fillna("Unknown")
    return out


def completed_visits(data):
    return data.loc[
        data.status.eq("completed") &
        data.appointment_outcome.eq("visit complete") &
        data.customer_id.notna()
    ].copy()


def prepare_reports(data):
    require_columns(data, ["report_id", "customer_id", "customer_viewed_date"])
    out = data.copy()
    if out.report_id.isna().any() or out.report_id.duplicated().any():
        raise ValueError("Report IDs must be unique. Investigate report join multiplicity.")
    out["customer_viewed_date"] = pd.to_datetime(
        out.customer_viewed_date, utc=True, format="mixed")
    return out.loc[out.customer_viewed_date.notna()].copy()


def label_satisfaction(data):
    out = data.copy()
    blank = out.patient_interaction_satisfaction.isna()
    out["score_status"] = "Recorded"
    out.loc[blank, "score_status"] = "Expectation unknown"
    out.loc[blank & out.visit_type.isin(VIDEO_TYPES), "score_status"] = "Missing"
    out.loc[blank & out.visit_type.eq("Async"), "score_status"] = "Not expected"
    return out
