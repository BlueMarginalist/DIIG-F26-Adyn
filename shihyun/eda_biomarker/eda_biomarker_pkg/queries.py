"""SQL only"""

# Birth control products, without the EXTERNAL and FREE placeholder skus
BC_SKUS = "sku like 'AD-BC-%' and sku not in ('AD-BC-EXTERNAL', 'AD-BC-FREE0000')"

OVERLAP = """
with h as (select distinct customer_id from hormonevalues),
     g as (select distinct customer_id from genotypevalues),
     r as (select distinct customer_id from rxorders)
select (select count(*) from h) as hormones,
       (select count(*) from g) as genotypes,
       (select count(*) from r) as prescriptions,
       (select count(*) from h join r using (customer_id)) as hormones_and_rx,
       (select count(*) from g join r using (customer_id)) as genotypes_and_rx,
       (select count(*) from h join g using (customer_id) join r using (customer_id)) as all_three
"""

SKU_SUMMARY = """
select sku, count(*) as orders, count(distinct customer_id) as customers,
       string_agg(distinct status, ', ') as statuses
from rxorders
group by sku
order by orders desc
"""

# One row per hormone result, including placeholders (cleaned in clean.py)
HORMONE_VALUES = """
select hv.customer_id, hv.sample_id, h.name as hormone,
       hv.hormone_value::float as value, hv.ref_low::float as ref_low,
       hv.ref_high::float as ref_high, hv.created_date
from hormonevalues hv join hormones h on h.id = hv.hormone_id
"""

RX_ORDERS = f"""
select customer_id, sku, date_order_placed
from rxorders
where {BC_SKUS}
"""

# Genetic scores per patient, from each patient's latest report
GENETICS = """
select distinct on (g.customer_id) g.customer_id,
  (rv.pipeline_output::jsonb #>> '{genetics,depprs,zscore}')::float as dep_zscore,
  (rv.pipeline_output::jsonb #>> '{genetics,vtesnp,F5_Leiden,risk_allele_count}')::int as f5_leiden,
  (rv.pipeline_output::jsonb #>> '{genetics,vtesnp,F2_Prothrombin,risk_allele_count}')::int as f2_prothrombin
from resultvalues rv
join (select distinct sample_id, customer_id from genotypevalues) g on g.sample_id = rv.dna_sample_id
order by g.customer_id, rv.created_date desc
"""

# Questionnaire answers stored in pipeline_output, per patient (latest report)
MEDBIO_ANSWER_KEYS = [
    "bc_goals", "bc_history", "concerns_about_menstrual_cycle", "experienced_previously",
    "high_trigs", "side_effects_to_avoid", "family_history", "interest_in_conceiving",
    "skip_periods", "smoker",
]
MEDBIO_ANSWERS = """
select distinct on (g.customer_id) g.customer_id,
""" + ",\n".join(f"  rv.pipeline_output::jsonb ->> '{k}' as {k}" for k in MEDBIO_ANSWER_KEYS) + """
from resultvalues rv
join (select distinct sample_id, customer_id from genotypevalues) g on g.sample_id = rv.dna_sample_id
order by g.customer_id, rv.created_date desc
"""

PIPELINE_KEYS = """
select key, jsonb_typeof(value) as type, count(*) as n_reports
from resultvalues, jsonb_each(pipeline_output::jsonb)
where pipeline_output is not null
group by key, type
order by n_reports desc, key
"""

GENETIC_FIELDS = """
select g.key as score, k.key as field, jsonb_typeof(k.value) as type, count(*) as n_reports
from resultvalues,
     jsonb_each(pipeline_output::jsonb -> 'genetics') g,
     jsonb_each(g.value) k
group by score, field, type
order by score, n_reports desc, field
"""

# --- North Star inputs. samples has no customer_id, so link through shipments -> orders.
# ASSUMPTION: orders has id and customer_id. Check with ORDERS_COLUMNS first.
SAMPLES = """
select o.customer_id, sa.id as sample_id, sa.kind, sa.status, sa.received_by_lab_date
from samples sa
join shipments sh on sh.id = sa.shipment_id
join orders o on o.id = sh.order_id
"""

MEDBIO_SUBMISSIONS = """
select customer_id, completion, created_date
from medicalbiosubmissions
"""

REPORTS = """
select id as report_id, dna_sample_id, hormone_sample_id, created_date,
       por_approved, adyn_approved, customer_viewed_date
from resultvalues
"""

# Checks (aggregates only)
SAMPLE_STATUS = "select kind, status, count(*) as n from samples group by kind, status order by kind, n desc"
MEDBIO_COMPLETION = "select completion, count(*) as n from medicalbiosubmissions group by completion order by n desc"
ORDERS_COLUMNS = """
select column_name, data_type from information_schema.columns
where table_name = 'orders' order by ordinal_position
"""
