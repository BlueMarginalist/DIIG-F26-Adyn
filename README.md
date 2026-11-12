# funnel_pkg: test completion funnel (fulfillment & sample return)

Reusable EDA for the adyn staging database, written by Michelle Zuo for workstream 1, following the layout of
`virtual_care_pkg` and `eda_biomarker_pkg`.

```
funnel_python/
  funnel_pkg/        the package
    config.py        every threshold and status name in one frozen dataclass (Config)
    db.py            Database: read-only psycopg 3 connection, reads credentials from the environment or a .env
    queries.py       SQL only (named %(params)s, no credentials, no names or emails)
    data.py          FunnelData: cached query results, refresh() to re-query
    clean.py         DataFrame in, DataFrame out (types, bulk-account split, groups)
    analysis.py      FunnelEDA: returns tables
    plots.py         FunnelPlots: returns matplotlib Figures
    demo.py          DemoData: synthetic stand-in for FunnelData (no database needed)
  make_plots.py      saves every chart (PNG) and its table (CSV)
  eda.ipynb          the walk-through notebook (runs on demo data by default)
  tests/             pytest (unit tests run anywhere; Postgres tests are opt-in)
```

## Setup

```powershell
pip install -e ".[database]"      # add ,dev for pytest
```

Credentials are never stored in this folder. Put them in a `.env` that is **not committed** (it is git-ignored), or set
them as environment variables in your shell:

```
ADYN_POSTGRES_HOST=...
ADYN_POSTGRES_PORT=5432
ADYN_POSTGRES_DB=...
ADYN_POSTGRES_USER=...
ADYN_POSTGRES_PASSWORD=...
```

The connection is read-only (`default_transaction_read_only=on`). Your IP must be allow-listed for the database.

## Use

```python
from funnel_pkg import Database, FunnelData, FunnelEDA, FunnelPlots

db = Database(env_file=".env")
eda = FunnelEDA(FunnelData(db))
eda.funnel()                       # table
FunnelPlots(eda).funnel()          # matplotlib Figure
db.close()
```

```powershell
python make_plots.py --demo                         # synthetic data, writes demo_output/
python make_plots.py --env-file .env --output output   # live database
```

`output/charts/*.png` are the pictures; `output/tables/*.csv` are the same numbers (counts only, no row-level data).

## Using it on production data

All settings live in `Config` (`funnel_pkg/config.py`). Likely changes:

- `timing_since`: staging has bulk-stamped shipping and lab dates, so timing is restricted to recent orders. Set it earlier if
  production dates are clean (check the `date_quality` table and chart first).
- `bulk_account_min_orders`, `replacement_pattern`, the status names, and the test-account patterns.
- `FunnelPlots(eda, data_note="")` removes the "Staging data" footnote.

## Tests

```powershell
pytest                                   # unit tests, no database
$env:ADYN_TEST_PG = "1"                  # also run the Postgres test against an EMPTY SCRATCH database (it wipes `public`)
```

`ADYN_TEST_REAL_SCHEMA=1` additionally runs every exploration query against a database that has the full adyn schema.

## Caveats

- Staging data contains testing records and bulk batches (see the cohort chart). Numbers are for method development, not reporting.
- Lab-side dates are batch-level in staging, so only paid to shipped and result created to approved timings are trustworthy.
