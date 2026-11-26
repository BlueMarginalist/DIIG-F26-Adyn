-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(distinct c.id) accounts, count(o.id) orders,
  count(o.id) filter (where o.status=%(reserved_status)s) reserved_orders,
  count(o.id) filter (where o.status=%(shipped_status)s) shipped_orders
from customers c join orders o on o.customer_id=c.id
where coalesce(o.name,'') not ilike %(replacement_pattern)s
  and (c.email ilike any(%(test_email_patterns)s) or c.first_name ilike %(test_name_pattern)s
       or c.last_name ilike %(test_name_pattern)s)
