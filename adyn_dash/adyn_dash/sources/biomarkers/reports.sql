-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select id as report_id, dna_sample_id, hormone_sample_id, created_date,
       por_approved, adyn_approved, customer_viewed_date, medbio_1_id,
       (pipeline_output::jsonb -> 'pipeline_runner_version' is not null) as new_pipeline,
       (pipeline_output::jsonb ->> 'bc_goals' is not null) as has_answers
from resultvalues
