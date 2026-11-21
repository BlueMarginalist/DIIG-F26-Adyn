# Adyn customer analytics

Backend analyses for the team dashboard. The active combined Python package is in
[`adyn_dash/`](adyn_dash/README.md), with setup and build instructions there.

| Area | Analyst | Module |
|---|---|---|
| Fulfillment and customer funnel | Michelle Zuo | `funnel` |
| Virtual care | Susan Li | `virtual_care` |
| Hormones, genetics and products | Shihyun Kim | `biomarkers` |
| Prescription journey | Morgan Kay | `prescriptions` |

All four modules use the same configuration, data store, SQL source layout, and
aggregate-table chart interface. Metric rules live in `adyn_dash/adyn_dash/metrics.py`.
The preliminary R notebook is retained as reference; Python does not replace every check.

See the [question-to-chart registry and demo audit](adyn_dash/docs/cleanup_review.md).
This cleanup is based on the supplied integration snapshot; Susan's newer dashboard
branch is separate and must be reconciled before a team merge. No branch has been merged.
