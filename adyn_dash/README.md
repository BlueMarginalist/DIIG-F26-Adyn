# adyn_dash

Back end for the Adyn dashboard: SQL in, tidy JSON out. The Quarto / Observable page reads the JSON files.

```
SQL sources  ->  DataStore (cached)  ->  AnalysisModule  ->  build.py  ->  dashboard/data/*.json + manifest.json
```

Four modules, one per analyst's work, all following the same interface:

| Module | Class | From | Charts |
|---|---|---|---|
| `virtual_care` | `VirtualCare` | Susan Li | repeat visits, gaps, report-to-booking wait, transitions, satisfaction |
| `biomarkers` | `Biomarkers` | Shihyun Kim | hormones, genetics, product choice, switching, North Star |
| `prescriptions` | `Prescriptions` | Morgan Kay | orders, quantities, approval flags, delays, shipments by state |
| `funnel` | `Funnel` | Michelle Zuo | order-to-result funnel, timing, replacements, date quality |

## Run it

```bash
pip install -e ".[test]"
python -m pytest
python -m adyn_dash.build --demo --out dashboard/data                  # synthetic data, no database
python -m adyn_dash.build --env-file .env --vc-data-through YYYY-MM-DD --out dashboard/data  # live; replace cutoff
python -m adyn_dash.build --demo --modules funnel,virtual_care         # a subset
```

Live mode needs `pip install -e ".[database]"` and these variables (never commit them):
`ADYN_POSTGRES_HOST`, `_PORT`, `_DB`, `_USER`, `_PASSWORD`. The session is opened read-only.

## Pointing it at the client's database

1. Set the `ADYN_POSTGRES_*` variables for the client's database and run the build without `--demo`.
2. If a table or column differs, copy the affected file from `adyn_dash/sources/<module>/<name>.sql` to a
   folder of your own and set `Config(sql_override_dir=...)`. A replacement query must return the columns
   declared on that `Source` (a missing column fails with the source's name).
3. Thresholds and patterns (replacement-order pattern, bulk-account cutoff, status names, cohort window) are
   fields on `Config`.

## How a module works

```python
class VirtualCare(AnalysisModule):
    name, title, owner = "virtual_care", "Virtual care and repeat visits", "Susan Li"
    sources = (Source("virtual_care", "appointments", ("id", "customer_id", ...)),)

    @chart("Completed visits per customer", "bar", x="visit_group", y="customer_ids", color="visit_type")
    def visit_frequency(self):
        return ...   # a tidy aggregate DataFrame; no customer-level rows
```

* A chart is a method marked `@chart(...)`. The decorator arguments are the chart spec; the build finds
  every marked method, so adding a chart needs no change to the build.
* `build` writes `<module>/<chart>.json` (a list of records) and `manifest.json` (spec, assumptions, row
  counts, status per chart). One failing chart is recorded with its error and the others still build.
* **Privacy guard:** a chart table with a person-level column (`customer_id`, `email`, ...) or more than
  `Config.max_output_rows` rows is rejected. Person-level work stays in memory.
* New module: add the class in `adyn_dash/modules/`, its SQL in `adyn_dash/sources/<module>/`, and register it
  in `modules/__init__.py`. Demo data comes from the class's `demo_sources(cfg)`.

## Chart spec (for the Observable layer)

| Field | Meaning |
|---|---|
| `title`, `note` | heading and the assumption text shown under the chart |
| `mark` | `bar`, `line`, `point`, `range` (`y` to `y2`), `heatmap`, `map` (US states) or `table` |
| `x`, `y`, `y2`, `color` | column names in the chart's table |
| `stack` | stack the colour groups instead of placing them side by side |
| `x_order` | category order for `x` |
| `filters` | columns the page should offer as filters |
| `internal` | data-quality chart for the team; hide from the client view |

## Layout

```
adyn_dash/
  config.py  source.py  database.py  module.py  build.py     shared framework
  modules/       one class per analyst's work (thin: sources, reshape, spec)
  lib/<topic>/   the analysts' own cleaning and analysis code, kept close to the original
  sources/<module>/*.sql
tests/
```

## Known limits

* **The demo bypasses SQL.** `DemoBackend` serves synthetic tables directly, so the `.sql` files are not run
  in demo mode. Only the framework and the Python logic are exercised. A seeded test database is the next step.
* Demo tests exercise Python logic, not SQL. Earlier local staging builds succeeded on the separate branches; the combined version must be rebuilt against staging before claiming live validation. Production compatibility remains unverified.
* **Some queries reference tables the analysts' scripts used** (for example `shippingaddresses`,
  `coupons_redeemers`, `customerintake`). If one is missing in the client database, that source fails and its
  charts are marked as empty states in the manifest; other query failures remain errors.
* The Quarto / Observable page is not part of this package yet.

## Integration cleanup: configuration and empty states

Install from the directory containing this README:

```bash
python -m pip install -e ".[database,dev]"
python -m pytest -q
python -m ruff check .
python -m adyn_dash.build --demo --out demo_output
python -m adyn_dash.build --env-file .env --out staging_output
```

Fill a local `.env` using `.env.example`, or set the same `ADYN_POSTGRES_*` environment
variables. This package uses one read-only Postgres connection for all modules. Credentials
are not written to exports. Do not upload `.env`, `.Renviron` or staging data.

An optional `ADYN_POSTGRES_SCHEMA` or `--schema` sets the connection search path using a
quoted SQL identifier. If omitted, the database role's existing search path is preserved.
The database must still have the expected tables, columns, types and JSON structure; changing
credentials cannot make incompatible schemas equivalent. For genuine structural differences,
`--sql-override-dir` accepts compatible SQL replacements returning the declared Source columns.
No SQL has been rewritten or business metric redefined by this cleanup.

Every module uses `AnalysisModule(DataStore(backend, Config), Config)` and returns aggregate
DataFrames from chart methods. Source SQL lives under `adyn_dash/sources/<module>/`; backend
connection/session setup remains in `database.py`. Defaults and metric definitions are centralized
in `metrics.py`; Config can override configurable defaults without editing analyses.
The repeated `require_columns` helper now lives in `validation.py`. Existing imports still work.
Prescription `patient_id` and customer account IDs are not renamed into equivalence: their mapping
has not been validated. Existing percent/share output names remain stable for compatibility.

Read every chart's `status` in `manifest.json`:

| Status | Meaning | Renderer action |
|---|---|---|
| `ok` | Analysis returned rows | Draw the table/chart |
| `empty` | Missing relation, empty source or no matching aggregate rows | Show `message`; do not draw stale values or fabricated zeros |
| `error` | Contract, permission, query or programming failure | Show an error indicator and investigate |

Empty/error chart files are overwritten with `[]` so an old successful build cannot silently supply
stale numbers. Other charts continue. An empty state is not proof that a metric equals zero.
`analysis_metadata`, when present, preserves the existing table attributes (such as excluded-delay counts).
The CLI returns nonzero for genuine chart errors; expected empty states do not make the build fail.
Connection/authentication failures still stop the run. Missing columns and permission failures remain
errors rather than being mislabeled as absent data. Missing reports no longer block visit-only charts.

The supplied standalone frontend still uses placeholder data and is not wired to these exports.
It must consume this status contract to display empty states in the UI. This backend change does
not make the existing static demo a live dashboard.

See [cleanup review](docs/cleanup_review.md) for source mappings, limitations, tests and merge guidance.

## Virtual care: run and inspect exports

Run these commands from the folder containing this README and `pyproject.toml` (the outer
`adyn_dash` folder, not the inner Python package):

```bash
python -m pip install -e ".[test,database]"
python -m pytest -q
python -m adyn_dash.build --demo --modules virtual_care --out demo_output
python -m adyn_dash.build --modules virtual_care --env-file ../.Renviron --vc-data-through 2026-03-04 --out staging_output
```

The last command reproduces the provisional staging analysis through March 4, 2026, inclusive
in UTC. Replace the date only when the available follow-up period is established. The latest
observed visit is not proof that data collection is complete through that date. The cutoff applies
to the four repeat-window exports; other virtual care charts use their full source data.
Use `--vc-window-days 90` to specify the repeat window (90 is the default).
Without an explicit live cutoff, the four repeat-window charts are recorded as errors.
The demo uses synthetic data and a separate aggregate repeat fixture; it does not test the SQL.

The build writes 18 chart tables under `staging_output/virtual_care/` and an index,
`staging_output/manifest.json`. Check each chart's `status`; the command exits with an error
if any chart fails. Internal charts are marked `spec.internal` and should remain hidden from
client-facing views. Generated staging output stays local and is ignored by Git.

Each virtual care manifest entry includes `export_metadata`:

- `entry_count` and `count_unit` identify the population or observations contributing to that chart.
  Counts may refer to customers, visits, report matches, visit pairs, or customer/type memberships.
  They are not interchangeable. Per-group counts and denominators remain in the chart tables.
- `missing_value_note` explains how missing values, Unknown categories and empty groups are handled.
- Where applicable, `completed_source_missing_counts` gives source-wide missing counts.
  These checks overlap and are not chart-specific exclusions or values to subtract from every chart.
- Report-wait exports also include aggregate matching counts. Metadata remains available even
  when a chart table is empty. JSON `null` represents an unavailable statistic, not zero.

Example inspection:

```bash
python - <<'PYCODE'
import json
from pathlib import Path
manifest = json.loads(Path("staging_output/manifest.json").read_text())
for chart in manifest["charts"]:
    if chart["module"] != "virtual_care":
        continue
    if chart["status"] != "ok":
        print(chart["id"], chart.get("message", chart.get("error", "Unavailable")))
        continue
    info = chart["export_metadata"]
    print(chart["id"], info["entry_count"], info["count_unit"])
    print("  Missing values:", info["missing_value_note"])
PYCODE
```

Database settings are `ADYN_POSTGRES_HOST`, `ADYN_POSTGRES_PORT`, `ADYN_POSTGRES_DB`,
`ADYN_POSTGRES_USER` and `ADYN_POSTGRES_PASSWORD`. `--env-file` is optional when these
are already set. Keep environment files local. See
[virtual care integration notes](docs_virtual_care_integration.md) for definitions and limitations.
