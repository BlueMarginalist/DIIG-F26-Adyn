# Backend follow-up: implemented changes and remaining work

Based on Susan's uploaded backend-sql-review.zip (reported commit 8c9c66c). No SQL tables
or clinical definitions were invented. Review this change before replacing the shared branch.

## Implemented

- Explicit environment files select an isolated, complete read-only database connection.
  Missing files/settings fail before connecting; literal dollar signs are preserved;
  process environment is not mutated; schema selection respects the selected configuration.
- Added viewer_noncompletion_status from the existing appointments and customer_cohort SQL
  sources, sharing the same eligibility logic as viewer_conversion. Unique customers are
  deduplicated within raw statuses; groups can overlap. No arbitrary latest-status rule is used.
- Added completed-visit denominators and percentages to score availability by modality.
  Unsupported score averages and five-point scales have not been fabricated.
- Manifest explicitly reports the lack of universal age/date filters.
- Added 10 regressions and updated the expected virtual-care export count from 18 to 19.

## Frontend changes the team can make using existing data

- Use viewer_conversion for report-view booking/completion conversion, naming the cohort
  and observation period and not claiming it responds to unsupported age/date controls.
- Use viewer_noncompletion_status for overlapping recorded status groups. Its chart labels
  must disclose overlap and the chosen denominator; it is not a mutually exclusive reasons chart.
- Use satisfaction with visit modalities (15-minute video, 25-minute video, Async, Unknown),
  availability statuses and percent_of_type. Do not label these as appointment purposes.
- Use approved_visit_frequency with its existing PoR-approved cohort and 0/1/2/3/4+ groups;
  do not imply Initial/Follow-up/Rx renewal/Lab review without a verified purpose source.
- Use repeat_overall/by_age/by_rx as descriptive explicit-window rates when that research
  question is desired; label the cutoff and completeness caveat. Provider groups stay internal.
  These tables cannot be used as the demo's logistic-regression odds ratios.
- Consume manifest ok/empty/error states and honor internal flags. Disable or remove
  unsupported global controls for these outputs rather than changing labels on fixed numbers.

## Remaining work that must not be called complete

1. Universal age/date controls require an agreed cohort, age reference date and event date
   for each measure (payment, viewing, visit completion, sampling). Applying a single
   timestamp predicate to every SQL source would change different questions differently.
2. The full 19-stage funnel and joint sample completion require verified milestone mappings
   and one consistent population. Existing shipping rates are not sample-completion rates.
3. No prediction model is available for the demo's odds ratios/hazard ratios. Replace that
   display with supported descriptive analyses or assign model work with an agreed outcome.
4. Hormone stratification requires verified exposure at sampling, ages, units and reference
   policies. First prescribed method is not current use, and no recorded Rx is not non-use.
5. Requested genetic phenotypes/variants beyond the queried fields require a schema/data-owner
   check. Missing code alone is not evidence that data is absent.
6. After deciding these definitions, implement/retest the appropriate SQL and frontend views.
   This patch addresses concrete current gaps; it does not complete every demo requirement.

## Validation

48 unittest checks pass in the isolated workspace, including 10 new follow-up checks.
A full demo build produces 75 ok exports, zero empty states and zero errors.
Pytest/Ruff are unavailable in this runtime; run the project's full checks on Susan's Mac.
No live database or production verification was performed here. Run staging with the
explicit provisional cutoff before committing any update.
