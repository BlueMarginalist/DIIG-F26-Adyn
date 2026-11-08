-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
with b as (
  select o.id, o.customer_id, o.date_order_paid paid_at, coalesce(o.por_approved,false) por_ok, o.status,
    (select min(p.created_date) from profilecompletions p where p.customer_id=o.customer_id and p.complete) profile_at,
    (select min(i.completed_date) from customerintake i where i.customer_id=o.customer_id and i.completed_date is not null) intake_at,
    (select min(h.completed_date) from medicalhistory h where h.customer_id=o.customer_id and h.completed_date is not null) medhist_at,
    (select min(os.created_date) from orderstatuses os where os.order_id=o.id and replace(os.new_status,'_',' ') = %(shipped_status)s) shipped_at
  from orders o join customers c on c.id=o.customer_id
  where coalesce(o.name,'') not ilike %(replacement_pattern)s and o.date_order_paid is not null and c.role = any(%(customer_roles)s)
    and (select count(*) from orders x where x.customer_id=c.id) < %(bulk_min)s
)

select case
    when shipped_at is not null then '5 shipped'
    when por_ok then '4 physician approved, not shipped'
    when profile_at is not null then '3 profile complete, not approved'
    else '1-2 paid, profile not complete' end furthest_step,
  count(*) orders from b group by 1 order by 1
