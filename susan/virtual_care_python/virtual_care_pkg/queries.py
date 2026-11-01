"""SQL retrieval, kept separate from analysis. No credentials belong here."""
APPOINTMENTS = """
SELECT id, customer_id, appointment_date, created_date,
       status, appointment_outcome, sku, patient_interaction_satisfaction
FROM appointments
"""
VIEWED_REPORTS = """
SELECT r.id AS report_id, r.customer_viewed_date, o.customer_id
FROM resultvalues AS r
LEFT JOIN samples AS s ON r.hormone_sample_id = s.id
LEFT JOIN shipments AS sh ON s.shipment_id = sh.id
LEFT JOIN orders AS o ON sh.order_id = o.id
WHERE r.customer_viewed_date IS NOT NULL
"""
