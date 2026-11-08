-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select distinct on (g.customer_id) g.customer_id,
  rv.pipeline_output::jsonb ->> 'bc_goals' as bc_goals,
  rv.pipeline_output::jsonb ->> 'bc_history' as bc_history,
  rv.pipeline_output::jsonb ->> 'concerns_about_menstrual_cycle' as concerns_about_menstrual_cycle,
  rv.pipeline_output::jsonb ->> 'experienced_previously' as experienced_previously,
  rv.pipeline_output::jsonb ->> 'high_trigs' as high_trigs,
  rv.pipeline_output::jsonb ->> 'side_effects_to_avoid' as side_effects_to_avoid,
  rv.pipeline_output::jsonb ->> 'family_history' as family_history,
  rv.pipeline_output::jsonb ->> 'interest_in_conceiving' as interest_in_conceiving,
  rv.pipeline_output::jsonb ->> 'skip_periods' as skip_periods,
  rv.pipeline_output::jsonb ->> 'smoker' as smoker
from resultvalues rv
join (select distinct sample_id, customer_id from genotypevalues) g on g.sample_id = rv.dna_sample_id
order by g.customer_id, rv.created_date desc
