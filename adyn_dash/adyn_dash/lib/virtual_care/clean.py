"""Small preparation functions. Inputs are copied, never modified in place."""
import pandas as pd

from ...metrics import (VISIT_TYPES, VIDEO_TYPES, SKU_TYPES, WAIT_GROUPS,
                        SCORE_STATUSES, COMPLETED_STATUS, COMPLETED_OUTCOME)


from ...validation import require_columns


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
        data.status.eq(COMPLETED_STATUS) &
        data.appointment_outcome.eq(COMPLETED_OUTCOME) &
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
