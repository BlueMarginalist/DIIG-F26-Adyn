-- Exploratory; cutoff completeness and UTC timestamp assumptions need confirmation.

WITH completed AS (
    SELECT customer_id, appointment_date, provider_id
    FROM appointments
    WHERE status = %(vc_completed_status)s AND appointment_outcome = %(vc_completed_outcome)s
      AND customer_id IS NOT NULL AND appointment_date IS NOT NULL
      AND appointment_date < %(vc_cutoff)s
), first_dates AS (
    SELECT customer_id, min(appointment_date) AS first_visit
    FROM completed GROUP BY customer_id
), first_providers AS (
    SELECT f.customer_id,
        CASE WHEN count(*) > 1 THEN 'Tied first visits'
             ELSE coalesce(min(a.provider_id::text), 'Missing provider')
        END AS provider_key
    FROM first_dates f JOIN completed a
      ON a.customer_id = f.customer_id AND a.appointment_date = f.first_visit
    GROUP BY f.customer_id
), eligible AS (
    SELECT f.*,
        extract(year FROM age(
            (f.first_visit AT TIME ZONE 'UTC')::date,
            c.date_of_birth::date)) AS baseline_age,
        p.provider_key,
        EXISTS (SELECT 1 FROM completed a
            WHERE a.customer_id = f.customer_id
              AND a.appointment_date > f.first_visit
              AND a.appointment_date <= f.first_visit + %(vc_window)s
        ) AS returned,
        CASE WHEN EXISTS (SELECT 1 FROM rxorders r
            WHERE r.customer_id = f.customer_id
              AND r.created_date AT TIME ZONE 'UTC' <= f.first_visit
        ) THEN 'Rx order recorded by first visit'
        WHEN EXISTS (SELECT 1 FROM rxorders r
            WHERE r.customer_id = f.customer_id AND r.created_date IS NULL
        ) THEN 'Unknown Rx timing'
        ELSE 'No Rx order recorded by first visit' END AS rx_group
    FROM first_dates f
    LEFT JOIN customers c ON c.id = f.customer_id
    JOIN first_providers p ON p.customer_id = f.customer_id
    WHERE f.first_visit + %(vc_window)s <= %(vc_cutoff)s
), categories AS (
    SELECT 'overall' AS factor, 'All eligible customers' AS category, returned
    FROM eligible
    UNION ALL
    SELECT 'age', CASE
        WHEN baseline_age IS NULL OR baseline_age < 0 OR baseline_age > 120
            THEN 'Unknown or invalid'
        WHEN baseline_age < 18 THEN 'Under 18'
        WHEN baseline_age < 30 THEN '18-29'
        WHEN baseline_age < 40 THEN '30-39'
        ELSE '40+' END, returned FROM eligible
    UNION ALL
    SELECT 'rx', rx_group, returned FROM eligible
    UNION ALL
    SELECT 'provider', provider_key, returned FROM eligible
)
SELECT factor, category, count(*) AS customers,
    count(*) FILTER (WHERE returned) AS repeat_customers,
    %(vc_cutoff)s::timestamptz AS cutoff_exclusive,
    %(vc_window_days)s::integer AS window_days
FROM categories GROUP BY factor, category ORDER BY factor, category
