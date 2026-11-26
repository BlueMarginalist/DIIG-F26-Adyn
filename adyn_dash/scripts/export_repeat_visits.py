"""Exploratory aggregate exports; run from the project directory containing pyproject.toml.

Uses the shared read-only backend. Does not export customer IDs, birth dates,
or provider IDs. This is an exploratory companion to the dashboard build.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from adyn_dash.database import PostgresBackend


from adyn_dash.config import Config
from adyn_dash.source import Source

SQL = Source("virtual_care", "repeat_summary").sql(Config())



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
    with PostgresBackend(env_file=args.env_file) as backend:
        with backend.conn.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute(SQL, Config(vc_data_through=args.data_through.isoformat(), vc_window_days=args.window_days).params())
            rows = [row[:4] for row in cursor.fetchall()]
    customers, repeats = export_rows(rows, args.out, args.data_through.isoformat(), args.window_days)
    print(f'Exported 4 summary tables as CSV and JSON to {args.out}')
    print(f'Eligible customers: {customers}; returned: {repeats}')
    print('Exploratory only: cutoff completeness and timestamp assumptions need confirmation.')


if __name__ == '__main__':
    main()
