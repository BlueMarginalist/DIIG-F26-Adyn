-- Result-level PoR approval, not order approval or adyn approval.
-- Hormone-sample linkage matches the existing report source; DNA-only and unlinked reports
-- cannot enter this cohort until their ownership path is validated against staging.
SELECT o.customer_id,
       bool_or(coalesce(r.por_approved, false)) AS por_approved,
       min(r.customer_viewed_date) AS first_viewed_date
FROM resultvalues r
JOIN samples s ON r.hormone_sample_id = s.id
JOIN shipments sh ON s.shipment_id = sh.id
JOIN orders o ON sh.order_id = o.id
WHERE o.customer_id IS NOT NULL
GROUP BY o.customer_id
