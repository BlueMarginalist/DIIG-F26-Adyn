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
