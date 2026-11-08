-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) n, round(percentile_cont(0.25) within group (order by extract(epoch from (m.received_by_lab_date - os.created_date))/86400)::numeric, 1) p25, round(percentile_cont(0.5) within group (order by extract(epoch from (m.received_by_lab_date - os.created_date))/86400)::numeric, 1) p50, round(percentile_cont(0.75) within group (order by extract(epoch from (m.received_by_lab_date - os.created_date))/86400)::numeric, 1) p75, round(percentile_cont(0.9) within group (order by extract(epoch from (m.received_by_lab_date - os.created_date))/86400)::numeric, 1) p90,
  count(*) filter (where m.received_by_lab_date < os.created_date) negative,
  count(*) filter (where m.received_by_lab_date > os.created_date + interval '90 days') over_90_days
from (select order_id, min(created_date) created_date from orderstatuses os where replace(os.new_status,'_',' ') = %(shipped_status)s group by 1) os
join orders o on o.id=os.order_id join shipments s on s.order_id=o.id
join (select shipment_id, min(received_by_lab_date) received_by_lab_date from samples group by 1) m on m.shipment_id=s.id
where coalesce(o.name,'') not ilike %(replacement_pattern)s and o.date_order_paid >= %(timing_since)s
