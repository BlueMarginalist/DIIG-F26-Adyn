-- Susan Li. One row per viewed report, linked to a customer through sample, shipment and order.
SELECT r.id AS report_id, r.customer_viewed_date, o.customer_id
FROM resultvalues AS r
LEFT JOIN samples AS s ON r.hormone_sample_id = s.id
LEFT JOIN shipments AS sh ON s.shipment_id = sh.id
LEFT JOIN orders AS o ON sh.order_id = o.id
WHERE r.customer_viewed_date IS NOT NULL
