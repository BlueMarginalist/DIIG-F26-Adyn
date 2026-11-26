-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) n, round(percentile_cont(0.25) within group (order by extract(epoch from (rv.created_date - m.received_by_lab_date))/86400)::numeric, 1) p25, round(percentile_cont(0.5) within group (order by extract(epoch from (rv.created_date - m.received_by_lab_date))/86400)::numeric, 1) p50, round(percentile_cont(0.75) within group (order by extract(epoch from (rv.created_date - m.received_by_lab_date))/86400)::numeric, 1) p75, round(percentile_cont(0.9) within group (order by extract(epoch from (rv.created_date - m.received_by_lab_date))/86400)::numeric, 1) p90
from orders o join shipments s on s.order_id=o.id join samples m on m.shipment_id=s.id
join resultvalues rv on m.id in (rv.dna_sample_id, rv.hormone_sample_id)
where coalesce(o.name,'') not ilike %(replacement_pattern)s and o.date_order_paid >= %(timing_since)s
