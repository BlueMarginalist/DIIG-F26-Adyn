-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select hv.customer_id, hv.sample_id, h.name as hormone,
       hv.hormone_value::float as value, hv.ref_low::float as ref_low,
       hv.ref_high::float as ref_high, hv.created_date
from hormonevalues hv join hormones h on h.id = hv.hormone_id
