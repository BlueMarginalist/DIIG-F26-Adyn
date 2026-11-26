"""Date columns audited by the funnel's date-quality check (table, column)."""
DATE_COLUMNS = [
    ("orders", "date_order_paid"), ("orders", "activation_date"), ("orders", "allied_order_date"),
    ("shipments", "date_shipped"), ("shipments", "delivered_to_customer_date"),
    ("shipments", "delivered_to_facility1_date"), ("samples", "received_by_lab_date"),
    ("samples", "processed_by_lab_date"), ("resultvalues", "created_date"),
    ("resultvalues", "customer_viewed_date"),
]
