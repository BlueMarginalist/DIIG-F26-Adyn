-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select date_trunc('month', o.date_order_paid)::date as paid_month, count(*) n from orders o
where coalesce(o.name,'') ilike %(replacement_pattern)s group by 1 order by 1
