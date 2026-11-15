# Virtual care validation

## PoR-approved denominator
The staging database check found 138 PoR-approved reports belonging
to 123 unique customers. All approved reports had a customer link.

Working definitions, pending confirmation:
- Visit-count distribution: unique customers with at least one
  PoR-approved result, including customers with zero completed visits.
- Report-view conversion: unique customers who viewed a report.

## First observed completed visit
Among 44 customers with dated completed visits:
- Video: 3
- Async: 3
- Unknown type: 37
- Multiple visits tied at the earliest timestamp: 1

These are first observed completed visits, not necessarily customers'
first-ever visits. Async-first records do not establish rule violations.

## Missing visit types
197 completed visits had missing SKUs. Keep these visits labeled
Unknown and include them in overall counts. Do not infer their type.

Missing visit types and potentially incomplete history prevent full
verification of the requirement that the first visit is synchronous.

## Exploratory 90-day repeat visits
Provisional observation cutoff: March 5, 2026 at 00:00 UTC,
including visits through March 4. Database completeness through this
date is unconfirmed.

Of 44 customers with dated completed visits, 41 had their first
observed visit at least 90 days before the cutoff.
18 of those 41 customers (43.9%) had another completed visit at a
strictly later timestamp within 90 days.

### Age at first observed visit
- Under 18: 1 of 2 returned (50.0%).
- 18-29: 12 of 23 returned (52.2%).
- 30-39: 5 of 13 returned (38.5%).
- 40+: 0 of 3 returned (0.0%).

### Prescription orders recorded by first visit
- Order recorded: 3 of 11 returned (27.3%).
- No order recorded: 15 of 30 returned (50.0%).
Order creation timestamps were assumed to be UTC.
Order presence does not establish medication use.

### Provider at first observed completed visit
Eight provider groups were observed, with sizes ranging from 1 to 14.
Three customers had a missing first-visit provider.
One customer had tied earliest visits and was kept separate.
Provider comparisons are too sparse and unadjusted for performance
rankings. Provider IDs have not been verified against NPIs.

### Interpretation
These are descriptive, unadjusted associations, not causal effects
or a validated prediction model. Earlier history may be missing.
The cohort includes customers with completed visits and is not
restricted to the PoR-approved cohort.
