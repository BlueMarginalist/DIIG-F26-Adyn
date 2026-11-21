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
python -m adyn_dash.build --env-file .env --out dashboard/data         # live, read-only
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
* **This cleanup has not been tested against the client database.** All 66 integration chart tables were
  exercised with demo data. Susan previously tested newer virtual care code on her separate branch; that
  does not validate this integration snapshot or the other modules against production.
* **Some queries reference tables the analysts' scripts used** (for example `shippingaddresses`,
  `coupons_redeemers`, `customerintake`). If one is missing in the client database, that source fails and its
  charts are marked as errors in the manifest.
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
