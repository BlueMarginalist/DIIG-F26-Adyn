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
* **The live Postgres path has not been run**, because no database was available. SQL is as the analysts wrote
  it (including Postgres-only JSON operators in `biomarkers`) except that it now lives in `.sql` files.
* **Some queries reference tables the analysts' scripts used** (for example `shippingaddresses`,
  `coupons_redeemers`, `customerintake`). If one is missing in the client database, that source fails and its
  charts are marked as errors in the manifest.
* The Quarto / Observable page is not part of this package yet.
