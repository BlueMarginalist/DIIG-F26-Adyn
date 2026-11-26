# Coverage update: what changed

Based on backend-cleanup fe92a4e and the supplied dashboard HTML (identical to the previous example).

## Added

- `funnel/delivered_kit_returns.json`: delivered shipments with 0, 1, or 2 sample-type lab receipts logged, plus invalid chronology. Original and replacement kits are separate. These are logged returns, not confirmed non-return or unique customers.
- `funnel/delivered_kit_both_valid.json`: percentage of delivered shipments with valid saliva AND blood samples on the same shipment. This is validity, not merely return, and not paid-customer completion.
- `biomarkers/dna_sample_quality.json`: unique DNA sample IDs by actual status, including Unknown. Conflicting statuses stop the export rather than double-count.
- `biomarkers/hormone_reference_summary.json`: INTERNAL review table. Measurement medians by recorded reference bounds; units remain unverified. Missing or invalid bounds give a null percentage, not zero. Never show this as client-ready.

The first two exports use logged outbound delivery as their denominator. Shipments without delivery logs are excluded and counted in `delivery_not_logged`. Sample receipts before delivery are flagged as invalid chronology in the return distribution. Validity is separately counted from recorded status, independent of date quality. No observation cutoff or fixed follow-up window is applied to these sample analyses. A sample with a missing receipt date does not establish a logged return. No shared age/date filters were added.

SQL groups samples and shipment-status events before joining, so duplicates cannot inflate kit counts. Only aggregate outputs are exported. The new source is read-only and uses fields already referenced by existing queries.

## Coverage review

`dashboard_coverage.csv` records all 91 items from the existing audit, including gaps and conditional mappings. Available exports still require frontend integration and validation. Internal data-quality outputs are not client charts. New outputs do not approve changing the original questions. The delivered-kit both-valid export is additional support, not an exact replacement for a paid-customer completion metric.

Still unresolved: a common cohort for the full journey and global filters; customer-controlled timing definitions; journey clustering and prediction models; visit-purpose labels; hormone units and exposure at sampling; score scale/meaning; and unavailable genetic fields. Do not invent these definitions or copy example values. The team must resolve these or explicitly defer them before claiming Task 2 complete. Quarto integration remains with Morgan and Shihyun.

## Verification of this update

- 10 new regression tests passed: duplicate joins, separate kits, missing delivery, invalid chronology, unknown sample status, conflicting records, zero denominators and reference-range coverage.
- 39 existing unittest-based tests passed (49 total with the new tests).
- Demo build: 79 exports, zero empty states, zero errors. This includes internal analyses.
- SQL aggregation exercised against SQLite fixtures; only PostgreSQL ILIKE was substituted. Live PostgreSQL/schema compatibility has NOT been tested here.
- Full pytest and Ruff were unavailable in this environment. Run both on Susan's Mac, then run staging. Prior successful 75-export staging run does not validate the four additions.
- Existing pandas warning remains. No changes were pushed or merged.
