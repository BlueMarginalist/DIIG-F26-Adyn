# Virtual care integration and handoff

## Run from the project directory containing pyproject.toml

```bash
python -m pytest -q
python -m adyn_dash.build --demo --modules virtual_care --out demo_output
python -m adyn_dash.build --modules virtual_care --env-file ../.Renviron --vc-data-through 2026-03-04 --out staging_output
```

The demo now has 18 registered chart tables (previously 13). Its repeat-summary
source is explicitly synthetic aggregate data: it tests the interface, not the SQL.
The live repeat charts require an explicit inclusive UTC cutoff. The chosen
2026-03-04 date is provisional, based on the latest observed completion, and is
not evidence that the database is complete through that date. A later confirmed
cutoff can be supplied with the same flag. --vc-window-days defaults to 90.
Existing non-repeat charts continue to use all observed records; the cutoff
applies only to the four repeat charts.

## Shared implementation within Susan's code

- lib/virtual_care/metrics.py: exact completion labels and SKU mappings, used by
  preparation and SQL parameters. Existing definitions are preserved.
- Config.vc_data_through, vc_window_days, vc_small_group: repeat reporting settings.
- sources/virtual_care/repeat_summary.sql: one shared aggregate query for the
  dashboard module and scripts/export_repeat_visits.py. The script remains usable
  for CSV plus JSON exports; it no longer contains a duplicate SQL implementation.
- First observed visit check is now repeatable through the standard module build.
- Four repeat outputs contain customers, repeat_customers, percent, small_group,
  cutoff_exclusive, window_days, and cutoff_completeness_confirmed=false.
- First-visit output reports a denominator and customers without dated visits.

## Interpretation and missing values

The repeat denominator is customers with dated completed visits whose earliest
observed completed visit allows the whole follow-up window before cutoff.
It is not the PoR-approved cohort or report-viewer cohort. Missing customer IDs
and visit dates are excluded from that calculation. Unknown SKUs remain included.
Only strictly later completions, up to and including the window endpoint, count.
Tied earliest completions remain eligible for overall/age/Rx calculations but
have no uniquely assigned first provider. They receive a separate provider group.

Age is evaluated at the first observed visit using completed calendar years.
Missing ages and ages outside 0-120 remain a separate Unknown or invalid group.
Rx means any order created by the first observed visit; no status filter is
applied. Unknown order timing is retained when there is no known earlier order.
Naive Rx timestamps are assumed UTC. Current order/customer fields may not fully
reconstruct historical state. Provider IDs have not been verified against NPIs.
Provider labels are temporary and can change across builds.

The sample is small, unadjusted, includes possible test accounts, and may have
incomplete earlier history. Do not interpret these comparisons as causation,
validated predictions, provider performance, or treatment effects. No confidence
intervals or significance claims are supplied. Small groups require review
before any public release; a flag alone does not de-identify an aggregate.

## Presentation choices ready for team discussion

Use bars with a zero baseline for age/Rx proportions. Display numerator and
denominator alongside each percentage and label the configured window/cutoff.
Do not stack Booked, Completed, and Booked without completion: these overlap.
Keep Unknown/missing categories visible and distinct from zero percentages.
An undefined percentage is null, never zero. Include counts for sparse groups.
Provider and first-visit diagnostic tables are marked internal in the manifest;
the frontend must honor that flag. Provider results should not become rankings.

Brand colors, a shared chart component, team-wide metric definitions, and any
changes to Michelle's funnel definitions remain for coordination. This update
does not claim those joint tasks are complete. Exact brand hex codes are not
invented here. No Quarto pages or front-end implementation are changed.

## Expected staging checks, if the snapshot is unchanged

First observed completed visits: Video 3, Async 3, Unknown 37, tied earliest 1.
Repeat overall: 41 eligible customers, 18 returning (43.9% rounded).
Age: Under 18 1/2; 18-29 12/23; 30-39 5/13; 40+ 0/3.
Rx recorded by first visit 3/11; none recorded 15/30.
Provider group totals should sum to 41 customers and 18 returns. These are
validation expectations, not demo values or hard-coded analysis results.

Generated staging exports are ignored by Git. Commit source/tests/documentation;
share aggregates only through the team's approved channel after review.
