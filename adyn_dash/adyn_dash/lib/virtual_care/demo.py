"""Artificial records for learning and testing. No real patient data."""
import pandas as pd


def synthetic_data():
    rows = []
    def add(customer, day, sku, score=None, status="completed", outcome="visit complete"):
        date = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=day)
        rows.append(dict(id=len(rows)+1, customer_id=customer, appointment_date=date,
                         created_date=date-pd.Timedelta(days=1), sku=sku,
                         status=status, appointment_outcome=outcome,
                         patient_interaction_satisfaction=score))
    add("demo-A", 1, "VC-SYNC-15CHRG", 0)
    add("demo-A", 5, "VC-ASYC-ADFREE")
    add("demo-A", 10, "VC-SYNC-15CHRG", 8)
    add("demo-A", 16, "VC-SYNC-15CHRG", 9)
    add("demo-A", 18, "VC-ASYC-ADCHRG")
    add("demo-B", 2, "VC-SYNC-25CHRG")
    add("demo-B", 4, None)
    add("demo-B", 8, None, 7)
    add("demo-C", 3, None)
    # Tied times test ambiguity in visit transitions.
    add("demo-C", 7, "VC-SYNC-15CHRG", 6)
    add("demo-C", 7, "VC-ASYC-ADFREE")
    add("demo-C", 9, None)
    add("demo-D", 20, "VC-SYNC-25CHRG", status="scheduled", outcome=None)
    reports = pd.DataFrame({
        "report_id": [101, 102, 103, 104, 105],
        "customer_id": ["demo-A", "demo-A", "demo-B", "demo-absent", None],
        "customer_viewed_date": ["2023-12-31", "2023-12-31", "2024-01-02",
                                 "2024-01-01", "2024-01-01"]})
    return pd.DataFrame(rows), reports
