-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) n, round(percentile_cont(0.25) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400)::numeric, 1) p25, round(percentile_cont(0.5) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400)::numeric, 1) p50, round(percentile_cont(0.75) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400)::numeric, 1) p75, round(percentile_cont(0.9) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400)::numeric, 1) p90,
  count(*) filter (where os.created_date < o.date_order_paid) negative
from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ') = %(shipped_status)s
where coalesce(o.name,'') not ilike %(replacement_pattern)s and o.date_order_paid >= %(timing_since)s
