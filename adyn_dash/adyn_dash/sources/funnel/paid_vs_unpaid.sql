-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select (o.date_order_paid is not null) paid,
  exists(select 1 from paymentissues p where p.customer_id=o.customer_id) has_payment_issue,
  count(*) orders
from orders o where coalesce(o.name,'') not ilike %(replacement_pattern)s group by 1,2 order by 1,2
