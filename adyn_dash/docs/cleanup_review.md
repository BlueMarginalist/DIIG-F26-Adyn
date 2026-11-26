# Integration cleanup and coverage review

## Scope and provenance

Based on the uploaded `DIIG-F26-Adyn-integration (1).zip`, the supplied
`Data Explorer_ Question prioritization.xlsx`, and `adyn-dashboard-standalone.html`.
This is a reviewable cleanup draft, not a production deployment or completed live-data audit.
All demo numbers and narratives are placeholders, not findings.

The integration ZIP has 66 charts and the older 10-chart virtual care module. It does not
contain Susan's 18-chart update, metadata notes, cohort/repeat SQL or prior R-file move.
Those changes were pushed separately through commit `8cad591`. They have not been
silently overwritten or represented as merged. Build a review branch from the current
integration branch and reconcile Susan's commits explicitly before merging.

## Review files

- `question_chart_registry.csv`: all 20 priority-rated questions, including Low, Medium,
  High and the two source values Highest (normalized to Very High while preserving original text).
- `all_questions_reference.csv`: all 40 populated question rows, including 20 unrated rows.
  Source question number 18 is duplicated; the added age/birth-control question is unnumbered.
  Stable IDs use original worksheet row numbers, e.g. RQ-R019 and RQ-R020.
- `demo_element_audit.csv`: 91 displayed metrics/cards/table rows, analytical insights and
  the shared filter contract across five tabs. Embedded funnel stage rows are audited separately
  in both places they appear. The overview funnel rows and journey count table are not assumed
  to be a single sequential cohort merely because the demo draws them in order.
- `chart_inventory.csv`: all 66 existing charts, their owners, internal flags and question/demo links.

Registry coverage Covered means the code addresses the stated question at its existing scope;
Partial means a related analysis exists but does not answer the whole question. Missing means
no matching analysis/export exists in this integration snapshot. A candidate from Susan's separate
branch is explicitly identified and never counted as integration-ready.

Demo status Ready requires the existing code to supply the actual requested metric, cohort,
grouping and stated filter behavior. Similar-looking data is not sufficient. The current demo
requires additional code/definition work across its exact displayed contracts, so its audit entries
are Needs code, often with useful partial candidates. This is not a claim that the backend has no
working charts. No data is reserved for confirmed absence of usable data; no client database was
available here, so source/pipeline absence is not invented. Review candidate mappings with owners.

## Important discrepancies

- Demo visit types Initial/Follow-up/Rx renewal/Lab review describe purpose; backend SKU types
  describe video duration/modality. A mapping cannot be inferred from the available code.
- Logistic-regression odds ratios and time-to-event hazard ratios have no matching models.
  Susan's separate age/Rx/provider repeat comparisons are descriptive, not such models.
- Score availability is physician-reported. A five-point average/customer satisfaction scale is not verified.
- Joint valid DNA+blood completion differs from kit shipped, marginal valid samples, or results viewed.
- Hormones by age and current birth-control exposure are not supplied by first-prescribed-method analyses.
- North Star uses a medical-biography completion proxy and is not restricted to a common paid cohort.
- Period/age controls in the demo filter synthetic weekly totals; many other figures are fixed.
  Do not present unfiltered backend statistics as responding to those controls.
- CYP2C19 and several demo variants are not extracted by current SQL. Inspect the actual pipeline
  before labeling their data unavailable. No genetic interpretation has been validated by this audit.

## Useful existing analyses absent from the demo

Consider the High-priority same-type first-to-last visit span (`virtual_care.visit_spans`).
For the rated Low-priority journey questions, `virtual_care.transitions` and
`virtual_care.video_to_async` already export useful aggregate tables. Same-type first/second/third
gaps and report-to-booking waits also exist but their source rows are unrated. For prescriptions,
orders/status/quantity and payment/packing delay exports exist but most Rx questions are unrated.
Do not expose internal quality tables, raw identifiers or small provider groups automatically.

## Completed cleanup

- One shared `metrics.py`: modality/product maps, waiting buckets, completion statuses, configurable
  business defaults, delay units/trim rule and group-size rules, with owner/rule/caveat records.
- Both cleaners share `validation.require_columns`; misplaced biomarker function docstrings corrected.
- Shared read-only database/config/data store retained; optional schema configured centrally.
- Missing tables and empty sources have explicit cached empty states. Actual code/permission/column
  errors stay errors. Old exported values are replaced with empty arrays when a chart cannot refresh.
- Visit-only charts no longer depend on report data unnecessarily.
- Root documentation and generated/local-file exclusions added. Ruff correctness checks configured.
- Existing published column names and identifier meanings preserved. Formatting is not used as an
  excuse to rewrite analyses or force incompatible account/patient identifiers together.

## Validation and practical limits

- All 41 pytest tests passed in Susan's cleanup workspace.
- Ruff passed the configured correctness checks.
- All 66 demo charts built successfully.
- All 66 charts built against staging with zero errors after fixing calendar-date JSON serialization.
- Demo date-conversion deprecation warnings and a pandas warning remain.
- Production database compatibility and frontend empty-state rendering have not been verified.
- Susan's newer virtual care branch still needs reconciliation before merging.

## Review order for Susan and Michelle

1. Work on a new integration-based review branch; preserve unrelated local files.
2. Apply this patch and review `git diff`. Do not blindly merge/replace the old analyst branches.
3. Reconcile Susan's separate virtual care commits, preserving her 18 exports and metadata.
4. Run tests, Ruff and all-module demo build; compare output schemas/results.
5. Test staging SQL using centrally configured connection settings. Validate source availability
   and approved metric definitions; record which modules were actually verified.
6. Review registry/audit disagreements with owners, then open a pull request targeting integration.

The analysis definitions intentionally preserve current assumptions. They do not prove the definitions
have been approved by Adyn, nor that matching table names imply compatible production data.
