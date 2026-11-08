-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select split_part(lower(c.email),'@',2) as email_domain, count(distinct c.id) as buyers, count(o.id) as orders,
  count(o.id) filter (where o.status=%(reserved_status)s) as reserved,
  count(o.id) filter (where o.status=%(shipped_status)s) as shipped
from customers c join orders o on o.customer_id=c.id where coalesce(o.name,'') not ilike %(replacement_pattern)s
group by 1 having count(distinct c.id) >= %(domain_min)s order by 3 desc limit 15
