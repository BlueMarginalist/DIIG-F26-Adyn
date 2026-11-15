"""Exploratory aggregate exports; run from the project directory containing pyproject.toml.

Uses the shared read-only backend. Does not export customer IDs, birth dates,
or provider IDs. This is an exploratory companion to the dashboard build.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from adyn_dash.database import PostgresBackend


SQL = """
WITH completed AS (
    SELECT customer_id, appointment_date, provider_id
    FROM appointments
    WHERE status = 'completed' AND appointment_outcome = 'visit complete'
      AND customer_id IS NOT NULL AND appointment_date IS NOT NULL
      AND appointment_date < %(cutoff)s
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
              AND a.appointment_date <= f.first_visit + %(window)s
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
    WHERE f.first_visit + %(window)s <= %(cutoff)s
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
    count(*) FILTER (WHERE returned) AS repeat_customers
FROM categories GROUP BY factor, category ORDER BY factor, category
"""


def export_rows(rows, output, cutoff_date, window_days):
    """Write only aggregate tables; provider labels are temporary per export."""
    tables = {factor: [] for factor in ('overall', 'age', 'rx', 'provider')}
    provider_number = 0
    for factor, category, customers, repeats in rows:
        customers, repeats = int(customers), int(repeats)
        if not 0 <= repeats <= customers:
            raise ValueError('Invalid repeat counts')
        if factor == 'provider' and category not in ('Missing provider', 'Tied first visits'):
            provider_number += 1
            category = f'Provider {provider_number}'
        tables[factor].append(dict(
            category=category, customers=customers, repeat_customers=repeats,
            repeat_percent=round(100 * repeats / customers, 1) if customers else None,
            small_group=customers < 5,
        ))
    totals = [(sum(r['customers'] for r in table),
               sum(r['repeat_customers'] for r in table)) for table in tables.values()]
    if len(set(totals)) != 1:
        raise ValueError('Factor totals disagree; no export written')
    output.mkdir(parents=True, exist_ok=True)
    fields = ['category', 'customers', 'repeat_customers', 'repeat_percent', 'small_group']
    for factor, table in tables.items():
        (output / f'repeat_by_{factor}.json').write_text(
            json.dumps(table, indent=2, allow_nan=False) + '\n')
        with (output / f'repeat_by_{factor}.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(table)
    metadata = dict(
        generated_at=datetime.now(timezone.utc).isoformat(),
        provisional_data_through=cutoff_date, window_days=window_days,
        eligible_customers=totals[0][0], repeat_customers=totals[0][1],
        assumptions=[
            'Data completeness through the provisional cutoff is unconfirmed.',
            'First observed completed visit is not necessarily first-ever visit.',
            'Completed means status completed and appointment_outcome visit complete.',
            'Include all visit types, including Unknown; exclude missing customer or visit date.',
            'Eligibility requires the entire window before the exclusive UTC cutoff.',
            'Return is a strictly later completed visit within the window, inclusive of its endpoint.',
            'Age is calculated at first observed visit; missing/invalid ages remain separate.',
            'Rx means any order created by first visit, not medication use or confirmed prescribing.',
            'Naive Rx creation timestamps are assumed UTC; current order status is not used.',
            'First-visit provider is separate when earliest visits tie; IDs are not validated NPIs.',
            'Provider numbers are temporary labels and may change across exports.',
            'Small groups are flagged below 5 customers; tables require review before public sharing.',
            'Descriptive unadjusted associations, not causal effects or validated predictions.',
            'Cohort is not restricted to PoR-approved customers; test accounts are not excluded.',
        ],
    )
    (output / 'repeat_visit_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return totals[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-through', required=True, type=date.fromisoformat)
    parser.add_argument('--window-days', type=int, default=90)
    parser.add_argument('--env-file', default='../.Renviron')
    parser.add_argument('--out', type=Path, default=Path('staging_output/repeat_visits'))
    args = parser.parse_args()
    if args.window_days <= 0:
        parser.error('--window-days must be positive')
    cutoff = datetime.combine(args.data_through + timedelta(days=1),
                              datetime.min.time(), tzinfo=timezone.utc)
    with PostgresBackend(env_file=args.env_file) as backend:
        with backend.conn.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute(SQL, dict(cutoff=cutoff, window=timedelta(days=args.window_days)))
            rows = cursor.fetchall()
    customers, repeats = export_rows(rows, args.out, args.data_through.isoformat(), args.window_days)
    print(f'Exported 4 summary tables as CSV and JSON to {args.out}')
    print(f'Eligible customers: {customers}; returned: {repeats}')
    print('Exploratory only: cutoff completeness and timestamp assumptions need confirmation.')


if __name__ == '__main__':
    main()
