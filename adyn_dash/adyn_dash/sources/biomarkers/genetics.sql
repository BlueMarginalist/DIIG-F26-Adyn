-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select distinct on (g.customer_id) g.customer_id,
  (rv.pipeline_output::jsonb #>> '{genetics,depprs,zscore}')::float as dep_zscore,
  (rv.pipeline_output::jsonb #>> '{genetics,vtesnp,F5_Leiden,risk_allele_count}')::int as f5_leiden,
  (rv.pipeline_output::jsonb #>> '{genetics,vtesnp,F2_Prothrombin,risk_allele_count}')::int as f2_prothrombin
from resultvalues rv
join (select distinct sample_id, customer_id from genotypevalues) g on g.sample_id = rv.dna_sample_id
order by g.customer_id, rv.created_date desc
