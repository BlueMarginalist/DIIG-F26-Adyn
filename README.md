# Adyn Customer Analytics

This project prepares data for the Adyn dashboard.

## Analysis areas

- Michelle: test fulfillment and sample returns
- Susan: virtual care
- Shihyun: hormones and genetics
- Morgan: prescriptions

## Useful links

- [Setup and run instructions](adyn_dash/README.md)
- [Shared metric definitions](adyn_dash/adyn_dash/metrics.py)
- [Cleanup notes and draft question/chart reviews](adyn_dash/docs/cleanup_review.md)

## Cleanup status

The cleanup is on the `backend-cleanup` branch for review.

- All 41 automated tests passed.
- The configured Ruff code checks passed.
- All 66 chart outputs built successfully against staging.

Michelle's review and combining Susan's newer virtual care updates
with this cleanup are still pending. Nothing has been merged into
`integration` yet.



