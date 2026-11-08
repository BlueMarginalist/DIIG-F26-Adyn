-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select exists(select 1 from orders r where r.customer_id=c.id and r.name ilike %(replacement_pattern)s) needed_replacement,
  count(*) shipped_customers,
  count(*) filter (where exists(
      select 1 from orders o2 join shipments s on s.order_id=o2.id join samples m on m.shipment_id=s.id
      join resultvalues rv on m.id in (rv.dna_sample_id, rv.hormone_sample_id)
      where o2.customer_id=c.id and rv.customer_viewed_date is not null)) viewed
from customers c
where exists(select 1 from orders o join shipments s on s.order_id=o.id where o.customer_id=c.id)
  and (select count(*) from orders x where x.customer_id=c.id) < %(bulk_min)s
group by 1
