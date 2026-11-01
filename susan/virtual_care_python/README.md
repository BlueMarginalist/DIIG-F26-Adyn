# Susan's virtual care EDA in Python

A simple object-oriented conversion of the consolidated virtual-care section
of Susan_Adyn_Analysis.qmd, plus the monthly and visit-transition analyses.
Your original R notebook stays unchanged.

## What is object-oriented here?

An object keeps related data and actions together:

```python
eda = VirtualCareEDA(appointments, reports)
summary = eda.visit_summary()
charts = VirtualCarePlots(eda)
figure = charts.visit_frequency()
```

`eda` holds prepared appointment/report data. Its methods return analysis tables.
`charts` uses those results and returns matplotlib Figures. Figures can be saved,
displayed in a notebook, or passed to a future dashboard. Methods do not print
patient records, save files, open a database connection, or display charts automatically.

## Relationship to Shihyun's example

The supplied reference uses `Database` and `AdynData` classes, cached queries,
and separate clean.py, analysis.py, plots.py and queries.py modules. This package
uses the same separation with `VirtualCareData`, and adds `VirtualCareEDA` and
`VirtualCarePlots` classes to meet the object-oriented request. It does not import
or modify Shihyun's package. Her hormone and prescription analyses are not part
of Susan's workstream.

## Folder placement

Inside your existing DIIG-F26-Adyn repository, create a folder named `susan`.
Place this entire `virtual_care_python` folder inside it:

    DIIG-F26-Adyn/susan/virtual_care_python/

The existing project .Renviron remains at DIIG-F26-Adyn/.Renviron.
Do not move or replace your original R notebook or your teammates' folders.

## Start with the synthetic example (Mac Terminal)

From your project folder:

```bash
cd ~/Documents/DIIG-F26-Adyn/susan/virtual_care_python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python make_plots.py --demo
```

If python3 is unavailable, install a Python 3.10+ interpreter through your
team's usual setup before continuing. This is independent of your R installation.

The demo creates eight PNG graphs and aggregate CSV summaries in demo_output/.
These values are ARTIFICIAL and must not be presented as project findings.
The included eda.ipynb runs the same analyses one question at a time.

## Run against the staging database

After the demo works, install the optional database dependencies:

```bash
python -m pip install -e '.[database]'
python make_plots.py --env-file ../../.Renviron
```

Run these from the package folder. Your network/IP must still be authorized
for database access. The loader expects the same ADYN_POSTGRES_HOST, PORT, DB,
USER, PASSWORD names as your R notebook. It reads .Renviron as dotenv-style
KEY=value entries and never overwrites existing environment variables.
R-specific expressions in .Renviron are not supported. No credentials are included.
The connection requests read-only transactions and closes after retrieval.

Live charts and aggregate summaries go in output/. Both output folders are
ignored by this package's .gitignore. Aggregate tables still require your team's
review before external sharing, especially with small samples.

## Files

| File | Responsibility |
|---|---|
| virtual_care_pkg/db.py | Optional read-only database connection |
| virtual_care_pkg/queries.py | SQL copied from the consolidated R retrieval |
| virtual_care_pkg/data.py | Cached raw tables and refresh method |
| virtual_care_pkg/clean.py | Type labels, input checks, date parsing, score labels |
| virtual_care_pkg/analysis.py | VirtualCareEDA analysis methods |
| virtual_care_pkg/plots.py | VirtualCarePlots graph methods |
| virtual_care_pkg/demo.py | Artificial records for examples/tests |
| eda.ipynb | Short notebook with one section per research question |
| make_plots.py | Runs the analyses and saves graphs/aggregate summaries |
| tests/test_analysis.py | Checks calculations, missingness, ties, and empty inputs |

## Eight questions and methods

| Question | Table method | Graph method on charts |
|---|---|---|
| 1. Visits per customer/type | visit_counts(), visit_summary(), visit_frequency() | visit_frequency() |
| 2. First-to-last span by type | visit_counts(), visit_summary() | visit_spans() |
| 3. First-to-second gap | visit_gaps(), gap_summary() | visit_gaps(), top panel |
| 4. Second-to-third gap | visit_gaps(), gap_summary() | visit_gaps(), bottom panel |
| 5. Report viewing to next appointment creation | report_waits(), report_summary(), report_type_summary(), report_wait_counts() | report_waits() |
| 6. Consecutive completed visit types | visit_transitions(), transition_table() | transitions() |
| 7. Async after most recent preceding known video | video_to_async(), async_summary() | video_to_async() |
| 8. Satisfaction availability | satisfaction_availability() | satisfaction() |

Supporting methods: monthly_visits() and quality_summary().
Supporting graph: monthly_visits(), with May 2024 marked as likely launch testing.

## Definitions and limitations preserved from R

- Staging data may contain testing records. No automatic test-account deletion.
- Completion requires BOTH status='completed' and outcome='visit complete', plus
  a customer ID. This definition is provisional. A customer ID is not a verified person ID.
- SKU mapping preserves the database spelling ASYC. Blank/unrecognized codes are
  Unknown. Input visit_type columns are replaced with this documented mapping.
- Counts include completed records with missing dates. Spans need two usable
  dates. Gaps are within the same type, with zero gaps retained. A span measures
  recorded activity, not total enrollment or observation time.
- No deduplication of customer/time records. IDs must be present and unique.
- Times are normalized to UTC. Naive timestamps are assumed UTC; confirm the
  source timezone before interpreting calendar-month boundaries.
- Unparseable dates raise errors. Repeated report IDs raise an error to expose
  join multiplicity instead of silently counting extra reports.
- Reports link through hormone sample -> shipment -> order -> customer. Gift
  purchases and report ownership still need validation. Reports without hormone
  sample links may lack a customer; they remain in report denominators and are
  counted explicitly in report_summary().
- Report waits use VIEWING and APPOINTMENT CREATION, all appointment statuses,
  one row per viewed report. They do not identify first-ever or first-completed
  care. Reports without a later match remain visible. An appointment may serve
  multiple reports. Tied first creations use smaller ID and flag first_time_ties.
- Async matching requires a strictly earlier video. Each async visit contributes
  once; a video may contribute to several async visits. Prior-video timestamp
  ties use smaller ID and flag video_time_ties. No refill or yearly-pattern claim.
- Satisfaction labels preserve numeric scores, including zero. Blank async scores
  are Not expected, blank known videos Missing, and blank Unknown visits have
  Expectation unknown. A nonblank async score stays Recorded for investigation.

## Deliberate correction to the R transition calculation

The earlier R code sorted by ID at equal timestamps and excluded only zero-time
pairs. It could still create an arbitrary transition into/out of those tied
visits. Python computes adjacency first and excludes every pair touching a tied
customer/time group. It never bridges over those records. Transition counts may
therefore differ from the old R table. Other definitions follow the consolidated R.

## Validation and next checks

```bash
python -m unittest discover -s tests -v
```

Ten synthetic-data tests cover spans/gaps, completion filtering, nearest prior
video, report reuse, unmatched reports, report ties, score zero, missing dates,
input copies, invalid IDs, caching, and empty table/plot outputs.

Live database access has NOT been tested here. Compare live results with the R
notebook before relying on them: previous screenshots showed 219 qualifying
visits, type counts 6/2/14/197, 107 viewed reports with 52 matched and 55 unmatched,
and six matched async visits across two customer IDs. These are historical
comparison values, not fixed targets if staging data has changed.

The package consolidates the eight research questions and supporting monthly EDA.
Early exploratory schema lookups and superseded duplicate R chunks remain in the
original notebook rather than being translated into production methods.

## Saving to GitHub

Review the new source files and run the demo first. Stage the new susan folder
explicitly; do not use git add . on the repository. Never commit credentials,
raw records, or a saved workspace image. Keep your susan-virtual-care branch.
