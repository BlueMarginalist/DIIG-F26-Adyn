-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) n,
  count(*) filter (where s.date_shipped < o.date_order_paid) shipped_before_paid,
  count(*) filter (where s.date_shipped < o.created_date) shipped_before_created,
  percentile_cont(0.5) within group (order by extract(epoch from (o.date_order_paid - o.created_date))/86400) med_paid_minus_created_days,
  percentile_cont(0.5) within group (order by extract(epoch from (s.date_shipped - o.created_date))/86400) med_shipped_minus_created_days
from orders o join shipments s on s.order_id=o.id where coalesce(o.name,'') not ilike %(replacement_pattern)s
