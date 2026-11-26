-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
with ord as (
  select o.id, o.customer_id, o.date_order_paid, o.status
  from orders o where coalesce(o.name,'') not ilike %(replacement_pattern)s
),
ord_c as (
  select customer_id, count(*) n_orders, min(date_order_paid) first_paid,
         count(*) filter (where status = %(reserved_status)s) n_reserved
  from ord group by 1
),
st as (
  select o.customer_id,
    min(os.created_date) filter (where replace(os.new_status,'_',' ') = %(sent_to_allied_status)s) sent_to_allied,
    min(os.created_date) filter (where replace(os.new_status,'_',' ') = %(shipped_status)s) shipped
  from ord o join orderstatuses os on os.order_id = o.id group by 1
),
chain as (
  select o.customer_id, m.id sample_id, m.received_by_lab_date, m.processed_by_lab_date
  from ord o join shipments s on s.order_id = o.id join samples m on m.shipment_id = s.id
),
samp_c as (
  select customer_id, min(received_by_lab_date) lab_received, min(processed_by_lab_date) lab_processed
  from chain group by 1
),
res_c as (
  select ch.customer_id, min(r.created_date) result_created,
         bool_or(coalesce(r.adyn_approved,false)) result_approved,
         min(r.customer_viewed_date) result_viewed
  from chain ch join resultvalues r on ch.sample_id in (r.dna_sample_id, r.hormone_sample_id)
  group by 1
),
appr as (
  select ch.customer_id, min(h.created_date) filter (where h.adyn_approved) result_approved_date
  from chain ch join resultvalueshistory h on ch.sample_id in (h.dna_sample_id, h.hormone_sample_id)
  group by 1
)
select c.id as customer_id, c.created_date,
  extract(year from age(c.created_date, c.date_of_birth)) as age_at_signup,
  sa.state,
  exists(select 1 from coupons_redeemers cr where cr.redeemer_id = c.id) gift_redeemer,
  exists(select 1 from couponorders co where co.customer_id = c.id) bought_gift,
  oc.n_orders, oc.n_reserved, oc.first_paid, st.sent_to_allied, st.shipped,
  sm.lab_received, sm.lab_processed, rc.result_created, rc.result_approved,
  ap.result_approved_date, rc.result_viewed
from customers c
left join ord_c oc on oc.customer_id = c.id
left join st on st.customer_id = c.id
left join samp_c sm on sm.customer_id = c.id
left join res_c rc on rc.customer_id = c.id
left join appr ap on ap.customer_id = c.id
left join shippingaddresses sa on sa.customer_id = c.id
