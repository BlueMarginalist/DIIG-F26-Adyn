-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select customer_id, completion, created_date
from medicalbiosubmissions
