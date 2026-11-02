import os, psycopg2

conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"], connect_timeout=10)
cur = conn.cursor()


def q(title, sql):
    print("\n== " + title)
    try:
        cur.execute(sql)
        print([d[0] for d in cur.description])
        for r in cur.fetchall():
            print(r)
    except Exception as e:
        conn.rollback()
        print("ERROR:", e)


def pct(expr):
    """p25/p50/p75/p90 of a day-difference expression, rounded."""
    return ", ".join(
        f"round(percentile_cont({p}) within group (order by {expr})::numeric, 1) p{int(p*100)}"
        for p in (0.25, 0.5, 0.75, 0.9))


REP = "coalesce(o.name,'') ilike '%replacement%'"
NOTREP = "coalesce(o.name,'') not ilike '%replacement%'"
LEFT = "replace(os.new_status,'_',' ') = 'left allied facility'"

print("##### PART 1: ARE THE UNSHIPPED ORDERS TEST / INTERNAL ACCOUNTS? (counts only) #####")

q("1a. buyers whose email/name looks like a test account",
  f"""select count(distinct c.id) accounts,
      count(o.id) orders,
      count(o.id) filter (where o.status='reserved') reserved_orders,
      count(o.id) filter (where o.status='left allied facility') shipped_orders
    from customers c join orders o on o.customer_id=c.id
    where {NOTREP}
      and (c.email ilike '%test%' or c.first_name ilike '%test%' or c.last_name ilike '%test%'
           or c.email ilike '%+%' or c.email ilike '%example.%' or c.email ilike '%mailinator%')""")

q("1b. email domains with 5+ buyers (domain only, no addresses)",
  f"""select split_part(lower(c.email),'@',2) domain, count(distinct c.id) buyers, count(o.id) orders,
      count(o.id) filter (where o.status='reserved') reserved,
      count(o.id) filter (where o.status='left allied facility') shipped
    from customers c join orders o on o.customer_id=c.id where {NOTREP}
    group by 1 having count(distinct c.id) >= 5 order by 3 desc limit 15""")

q("1c. IP addresses used by 5+ orders (counts only, IPs not shown)",
  f"""select count(*) shared_ip_groups, sum(n) orders_in_groups, sum(reserved) reserved_in_groups from (
      select o.ip, count(*) n, count(*) filter (where o.status='reserved') reserved
      from orders o where {NOTREP} and o.ip is not null group by 1 having count(*) >= 5) t""")

q("1d. account roles that are staff / providers (0 admin, 1 editor, 5 physician)",
  f"""select c.role, count(distinct c.id) accounts, count(o.id) orders,
      count(o.id) filter (where o.status='reserved') reserved
    from customers c join orders o on o.customer_id=c.id where {NOTREP} and c.role in (0,1,5)
    group by 1 order by 1""")

q("1e. orders placed but unpaid vs paid, by whether payment issue exists",
  f"""select (o.date_order_paid is not null) paid,
      exists(select 1 from paymentissues p where p.customer_id=o.customer_id) has_payment_issue,
      count(*) from orders o where {NOTREP} group by 1,2 order by 1,2""")

print("\n\n##### PART 2: REPLACEMENT KITS #####")

q("2a. replacement orders per customer (how many patients needed 1, 2, 3...)",
  f"""select n_rep, count(*) customers from (
      select o.customer_id, count(*) n_rep from orders o where {REP} group by 1) t
    group by 1 order by 1""")

q("2b. replacement reason (shipments_replacements.reason; values seen 2+ times)",
  """select left(coalesce(reason,'(blank)'),60) reason, count(*) from shipments_replacements
    group by 1 having count(*) >= 2 order by 2 desc limit 20""")

q("2c. replacement table totals",
  """select count(*) rows, count(distinct old_shipment_id) distinct_old_shipments,
      count(reimbursed_date) reimbursed from shipments_replacements""")

q("2d. status of the ORIGINAL samples that were replaced (what failed: kind + status)",
  """select m.kind, coalesce(m.status,'(blank)') status, count(*) from shipments_replacements r
    join samples m on m.shipment_id = r.old_shipment_id group by 1,2 order by 3 desc""")

q("2e. replacement orders by product name",
  f"""select o.name, o.sku, count(*) from orders o where {REP} group by 1,2 order by 3 desc""")

q("2f. replacement orders by paid month",
  f"""select date_trunc('month', o.date_order_paid)::date as paid_month, count(*) from orders o
    where {REP} group by 1 order by 1""")

q("2g. do customers who needed a replacement still view results? (original-order customers)",
  f"""select exists(select 1 from orders r where r.customer_id=c.id and r.name ilike '%replacement%') needed_replacement,
      count(*) shipped_customers,
      count(*) filter (where exists(
          select 1 from orders o2 join shipments s on s.order_id=o2.id join samples m on m.shipment_id=s.id
          join resultvalues rv on m.id in (rv.dna_sample_id, rv.hormone_sample_id)
          where o2.customer_id=c.id and rv.customer_viewed_date is not null)) viewed
    from customers c
    where exists(select 1 from orders o join shipments s on s.order_id=o.id where o.customer_id=c.id)
      and (select count(*) from orders x where x.customer_id=c.id) < 10
    group by 1""")

print("\n\n##### PART 3: TIMING BETWEEN STEPS (days; only orders paid 2023-01-01 or later, to avoid the bulk-stamped 2022 dates) #####")

q("3a. paid -> left Allied (shipped)",
  f"""select count(*) n, {pct('extract(epoch from (os.created_date - o.date_order_paid))/86400')},
      count(*) filter (where os.created_date < o.date_order_paid) negative
    from orders o join orderstatuses os on os.order_id=o.id and {LEFT}
    where {NOTREP} and o.date_order_paid >= '2023-01-01'""")

q("3b. left Allied -> sample received by lab (negative = date not trustworthy)",
  f"""select count(*) n, {pct('extract(epoch from (m.received_by_lab_date - os.created_date))/86400')},
      count(*) filter (where m.received_by_lab_date < os.created_date) negative,
      count(*) filter (where m.received_by_lab_date > os.created_date + interval '90 days') over_90_days
    from (select order_id, min(created_date) created_date from orderstatuses os where {LEFT} group by 1) os
    join orders o on o.id=os.order_id join shipments s on s.order_id=o.id
    join (select shipment_id, min(received_by_lab_date) received_by_lab_date from samples group by 1) m on m.shipment_id=s.id
    where {NOTREP} and o.date_order_paid >= '2023-01-01'""")

q("3c. sample received -> result created",
  f"""select count(*) n, {pct('extract(epoch from (rv.created_date - m.received_by_lab_date))/86400')}
    from orders o join shipments s on s.order_id=o.id join samples m on m.shipment_id=s.id
    join resultvalues rv on m.id in (rv.dna_sample_id, rv.hormone_sample_id)
    where {NOTREP} and o.date_order_paid >= '2023-01-01'""")

q("3d. result created -> approved (approval time from the history table)",
  f"""select count(*) n,
      {pct('extract(epoch from (a.approved_at - rv.created_date))/86400')}
    from resultvalues rv
    join (select result_values_id, min(created_date) approved_at from resultvalueshistory
          where adyn_approved group by 1) a on a.result_values_id = rv.id""")

q("3e. real outbound/return timing from shipmentstatuses (2024-04 onward only)",
  """select count(*) shipments,
      count(*) filter (where out_delivered is not null) delivered_to_customer_logged,
      count(*) filter (where ret1_delivered is not null) saliva_return_logged,
      count(*) filter (where ret2_delivered is not null) blood_return_logged,
      round(percentile_cont(0.5) within group (order by extract(epoch from (ret1_delivered-out_delivered))/86400)::numeric,1) med_days_saliva_back,
      round(percentile_cont(0.5) within group (order by extract(epoch from (ret2_delivered-out_delivered))/86400)::numeric,1) med_days_blood_back,
      round(percentile_cont(0.9) within group (order by extract(epoch from (ret2_delivered-out_delivered))/86400)::numeric,1) p90_days_blood_back
    from (select shipment_id,
        min(created_date) filter (where status='delivered') out_delivered,
        min(created_date) filter (where return_status1='delivered') ret1_delivered,
        min(created_date) filter (where return_status2='delivered') ret2_delivered
      from shipmentstatuses group by 1) t""")

print("\n\n##### PART 4: BLOCKING STEPS BETWEEN PAYMENT AND SHIPPING (paid, non-replacement, customer/purchaser roles, bulk accounts excluded) #####")

BASE = f"""
with b as (
  select o.id, o.customer_id, o.date_order_paid paid_at, coalesce(o.por_approved,false) por_ok, o.status,
    (select min(p.created_date) from profilecompletions p where p.customer_id=o.customer_id and p.complete) profile_at,
    (select min(i.completed_date) from customerintake i where i.customer_id=o.customer_id and i.completed_date is not null) intake_at,
    (select min(h.completed_date) from medicalhistory h where h.customer_id=o.customer_id and h.completed_date is not null) medhist_at,
    (select min(os.created_date) from orderstatuses os where os.order_id=o.id and {LEFT}) shipped_at
  from orders o join customers c on c.id=o.customer_id
  where {NOTREP} and o.date_order_paid is not null and c.role in (2,3)
    and (select count(*) from orders x where x.customer_id=c.id) < 10
)
"""

q("4a. furthest step each paid order reached",
  BASE + """select case
        when shipped_at is not null then '5 shipped'
        when por_ok then '4 physician approved, not shipped'
        when profile_at is not null then '3 profile complete, not approved'
        else '1-2 paid, profile not complete' end furthest_step,
      count(*) orders from b group by 1 order by 1""")

q("4b. does profile completion come BEFORE shipping? (sequence check on shipped orders)",
  BASE + """select count(*) shipped_orders,
      count(*) filter (where profile_at is null) no_profile_record,
      count(*) filter (where profile_at <= shipped_at) profile_before_ship,
      count(*) filter (where profile_at > shipped_at) profile_after_ship
    from b where shipped_at is not null""")

q("4c. days from payment to profile complete (orders that did complete it)",
  BASE + f"""select count(*) n, {pct('extract(epoch from (profile_at - paid_at))/86400')},
      count(*) filter (where profile_at < paid_at) profile_before_payment,
      count(*) filter (where profile_at > paid_at + interval '30 days') over_30_days,
      count(*) filter (where profile_at > paid_at + interval '90 days') over_90_days
    from b where profile_at is not null""")

q("4d. optional forms among orders that stalled after profile (intake / medical history)",
  BASE + """select (shipped_at is not null) shipped, count(*) orders,
      count(*) filter (where intake_at is not null) intake_done,
      count(*) filter (where medhist_at is not null) medhist_done
    from b where profile_at is not null group by 1""")

q("4e. paid orders by paid year: share reaching each step",
  BASE + """select extract(year from paid_at)::int yr, count(*) paid,
      count(*) filter (where profile_at is not null) profile_done,
      count(*) filter (where por_ok) physician_ok,
      count(*) filter (where shipped_at is not null) shipped
    from b group by 1 order by 1""")

q("4f. medical biography submissions (early customers): completion value vs shipped",
  BASE + """select mb.completion, count(distinct b.id) orders,
      count(distinct b.id) filter (where b.shipped_at is not null) shipped
    from b join medicalbiosubmissions mb on mb.customer_id=b.customer_id group by 1 order by 1""")

conn.close()
