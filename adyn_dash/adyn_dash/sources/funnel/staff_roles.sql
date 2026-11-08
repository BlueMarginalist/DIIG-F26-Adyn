-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select c.role, count(distinct c.id) accounts, count(o.id) orders,
  count(o.id) filter (where o.status=%(reserved_status)s) reserved
from customers c join orders o on o.customer_id=c.id
where coalesce(o.name,'') not ilike %(replacement_pattern)s and c.role = any(%(staff_roles)s)
group by 1 order by 1
