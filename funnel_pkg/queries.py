"""SQL only, kept separate from analysis. No credentials belong here.

Queries use named parameters (%(name)s) filled from Config.params(); there are no literal percent
signs (patterns such as '%replacement%' are passed as parameters). Only counts and dates are returned,
never names, emails or addresses.
"""
# ---- shared fragments -----------------------------------------------------------------------
NOT_REPLACEMENT = "coalesce(o.name,'') not ilike %(replacement_pattern)s"
IS_REPLACEMENT = "coalesce(o.name,'') ilike %(replacement_pattern)s"
LEFT_ALLIED = "replace(os.new_status,'_',' ') = %(shipped_status)s"
SENT_TO_ALLIED = "replace(os.new_status,'_',' ') = %(sent_to_allied_status)s"


def pct(expr: str) -> str:
    """p25/p50/p75/p90 of a day-difference expression."""
    return ", ".join(
        f"round(percentile_cont({p}) within group (order by {expr})::numeric, 1) p{int(p * 100)}"
        for p in (0.25, 0.5, 0.75, 0.9)
    )


# ---- customer-level funnel (funnel_v2.py) ----------------------------------------------------
CUSTOMER_FUNNEL = f"""
with ord as (
  select o.id, o.customer_id, o.date_order_paid, o.status
  from orders o where {NOT_REPLACEMENT}
),
ord_c as (
  select customer_id, count(*) n_orders, min(date_order_paid) first_paid,
         count(*) filter (where status = %(reserved_status)s) n_reserved
  from ord group by 1
),
st as (
  select o.customer_id,
    min(os.created_date) filter (where {SENT_TO_ALLIED}) sent_to_allied,
    min(os.created_date) filter (where {LEFT_ALLIED}) shipped
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
"""

# ---- saliva vs blood (funnel_v2.py, diag3.py) ---------------------------------------------------
KIT_OUTCOMES = """
select (coalesce(o.name,'') ilike %(replacement_pattern)s) is_replacement, count(*) shipments,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV')) has_saliva,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV' and m.status='valid')) saliva_valid,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD')) has_blood,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD' and m.status='valid')) blood_valid
from shipments s join orders o on o.id = s.order_id group by 1 order by 1
"""
SAMPLE_STATUS_BY_KIND = "select kind, status, count(*) n from samples group by 1,2 order by 1,3 desc"

# ---- test / internal accounts (next_analysis.py part 1, fix_queries.py) --------------------------------
TEST_LIKE_ACCOUNTS = f"""
select count(distinct c.id) accounts, count(o.id) orders,
  count(o.id) filter (where o.status=%(reserved_status)s) reserved_orders,
  count(o.id) filter (where o.status=%(shipped_status)s) shipped_orders
from customers c join orders o on o.customer_id=c.id
where {NOT_REPLACEMENT}
  and (c.email ilike any(%(test_email_patterns)s) or c.first_name ilike %(test_name_pattern)s
       or c.last_name ilike %(test_name_pattern)s)
"""
EMAIL_DOMAINS = f"""
select split_part(lower(c.email),'@',2) as email_domain, count(distinct c.id) as buyers, count(o.id) as orders,
  count(o.id) filter (where o.status=%(reserved_status)s) as reserved,
  count(o.id) filter (where o.status=%(shipped_status)s) as shipped
from customers c join orders o on o.customer_id=c.id where {NOT_REPLACEMENT}
group by 1 having count(distinct c.id) >= %(domain_min)s order by 3 desc limit 15
"""
SHARED_IPS = f"""
select count(*) as shared_ip_groups, sum(n) as orders_in_groups, sum(reserved) as reserved_in_groups from (
  select o.ip, count(*) n, count(*) filter (where o.status=%(reserved_status)s) reserved
  from orders o where {NOT_REPLACEMENT} and o.ip is not null group by 1 having count(*) >= %(shared_ip_min)s) t
"""
STAFF_ROLES = f"""
select c.role, count(distinct c.id) accounts, count(o.id) orders,
  count(o.id) filter (where o.status=%(reserved_status)s) reserved
from customers c join orders o on o.customer_id=c.id
where {NOT_REPLACEMENT} and c.role = any(%(staff_roles)s)
group by 1 order by 1
"""
PAID_VS_UNPAID = f"""
select (o.date_order_paid is not null) paid,
  exists(select 1 from paymentissues p where p.customer_id=o.customer_id) has_payment_issue,
  count(*) orders
from orders o where {NOT_REPLACEMENT} group by 1,2 order by 1,2
"""
ORDER_STATUS_TOTALS = f"""
select count(*) non_replacement_orders, count(*) filter (where o.status=%(reserved_status)s) reserved
from orders o where {NOT_REPLACEMENT}
"""

# ---- replacement kits (next_analysis.py part 2, fix_queries.py) -------------------------------------------
REP_PER_CUSTOMER = f"""
select n_rep, count(*) customers from (
  select o.customer_id, count(*) n_rep from orders o where {IS_REPLACEMENT} group by 1) t
group by 1 order by 1
"""
REP_REASONS = """
select left(coalesce(reason,'(blank)'),60) reason, count(*) n from shipments_replacements
group by 1 having count(*) >= %(reason_min_count)s order by 2 desc limit 20
"""
REP_REASON_CLASSES = """
select count(*) as total,
  count(*) filter (where reason ilike %(placeholder_like_pattern)s
                   or lower(reason) = any(%(placeholder_reasons)s)) as placeholder_like,
  count(*) filter (where reason ilike any(%(structured_prefixes)s)) as structured_real
from shipments_replacements
"""
REP_TOTALS = """
select count(*) as n_rows, count(distinct old_shipment_id) as distinct_old_shipments,
  count(reimbursed_date) as reimbursed from shipments_replacements
"""
REP_ORIGINAL_SAMPLE_STATUS = """
select m.kind, coalesce(m.status,'(blank)') status, count(*) n from shipments_replacements r
join samples m on m.shipment_id = r.old_shipment_id group by 1,2 order by 3 desc
"""
REP_BY_PRODUCT = f"""
select o.name, o.sku, count(*) n from orders o where {IS_REPLACEMENT} group by 1,2 order by 3 desc
"""
REP_BY_MONTH = f"""
select date_trunc('month', o.date_order_paid)::date as paid_month, count(*) n from orders o
where {IS_REPLACEMENT} group by 1 order by 1
"""
REP_VS_VIEWING = """
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
"""

# ---- timing between steps (next_analysis.py part 3) ------------------------------------------------------
PAID_TO_SHIPPED = f"""
select count(*) n, {pct('extract(epoch from (os.created_date - o.date_order_paid))/86400')},
  count(*) filter (where os.created_date < o.date_order_paid) negative
from orders o join orderstatuses os on os.order_id=o.id and {LEFT_ALLIED}
where {NOT_REPLACEMENT} and o.date_order_paid >= %(timing_since)s
"""
SHIPPED_TO_LAB = f"""
select count(*) n, {pct('extract(epoch from (m.received_by_lab_date - os.created_date))/86400')},
  count(*) filter (where m.received_by_lab_date < os.created_date) negative,
  count(*) filter (where m.received_by_lab_date > os.created_date + interval '90 days') over_90_days
from (select order_id, min(created_date) created_date from orderstatuses os where {LEFT_ALLIED} group by 1) os
join orders o on o.id=os.order_id join shipments s on s.order_id=o.id
join (select shipment_id, min(received_by_lab_date) received_by_lab_date from samples group by 1) m on m.shipment_id=s.id
where {NOT_REPLACEMENT} and o.date_order_paid >= %(timing_since)s
"""
LAB_TO_RESULT = f"""
select count(*) n, {pct('extract(epoch from (rv.created_date - m.received_by_lab_date))/86400')}
from orders o join shipments s on s.order_id=o.id join samples m on m.shipment_id=s.id
join resultvalues rv on m.id in (rv.dna_sample_id, rv.hormone_sample_id)
where {NOT_REPLACEMENT} and o.date_order_paid >= %(timing_since)s
"""
RESULT_TO_APPROVED = f"""
select count(*) n, {pct('extract(epoch from (a.approved_at - rv.created_date))/86400')}
from resultvalues rv
join (select result_values_id, min(created_date) approved_at from resultvalueshistory
      where adyn_approved group by 1) a on a.result_values_id = rv.id
"""
RETURN_TIMING = """
select count(*) shipments,
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
  from shipmentstatuses group by 1) t
"""

# ---- blocking steps between payment and shipping (next_analysis.py part 4, fix_queries.py 4g) ----------------
BLOCKING_BASE = f"""
with b as (
  select o.id, o.customer_id, o.date_order_paid paid_at, coalesce(o.por_approved,false) por_ok, o.status,
    (select min(p.created_date) from profilecompletions p where p.customer_id=o.customer_id and p.complete) profile_at,
    (select min(i.completed_date) from customerintake i where i.customer_id=o.customer_id and i.completed_date is not null) intake_at,
    (select min(h.completed_date) from medicalhistory h where h.customer_id=o.customer_id and h.completed_date is not null) medhist_at,
    (select min(os.created_date) from orderstatuses os where os.order_id=o.id and {LEFT_ALLIED}) shipped_at
  from orders o join customers c on c.id=o.customer_id
  where {NOT_REPLACEMENT} and o.date_order_paid is not null and c.role = any(%(customer_roles)s)
    and (select count(*) from orders x where x.customer_id=c.id) < %(bulk_min)s
)
"""
FURTHEST_STEP = BLOCKING_BASE + """
select case
    when shipped_at is not null then '5 shipped'
    when por_ok then '4 physician approved, not shipped'
    when profile_at is not null then '3 profile complete, not approved'
    else '1-2 paid, profile not complete' end furthest_step,
  count(*) orders from b group by 1 order by 1
"""
PROFILE_SEQUENCE = BLOCKING_BASE + """
select count(*) shipped_orders,
  count(*) filter (where profile_at is null) no_profile_record,
  count(*) filter (where profile_at <= shipped_at) profile_before_ship,
  count(*) filter (where profile_at > shipped_at) profile_after_ship
from b where shipped_at is not null
"""
PROFILE_DAYS = BLOCKING_BASE + f"""
select count(*) n, {pct('extract(epoch from (profile_at - paid_at))/86400')},
  count(*) filter (where profile_at < paid_at) profile_before_payment,
  count(*) filter (where profile_at > paid_at + interval '30 days') over_30_days,
  count(*) filter (where profile_at > paid_at + interval '90 days') over_90_days
from b where profile_at is not null
"""
OPTIONAL_FORMS = BLOCKING_BASE + """
select (shipped_at is not null) shipped, count(*) orders,
  count(*) filter (where intake_at is not null) intake_done,
  count(*) filter (where medhist_at is not null) medhist_done
from b where profile_at is not null group by 1
"""
STEPS_BY_YEAR = BLOCKING_BASE + """
select extract(year from paid_at)::int yr, count(*) paid,
  count(*) filter (where profile_at is not null) profile_done,
  count(*) filter (where por_ok) physician_ok,
  count(*) filter (where shipped_at is not null) shipped
from b group by 1 order by 1
"""
MEDBIO = BLOCKING_BASE + """
select mb.completion, count(distinct b.id) orders,
  count(distinct b.id) filter (where b.shipped_at is not null) shipped
from b join medicalbiosubmissions mb on mb.customer_id=b.customer_id group by 1 order by 1
"""
COHORT_BY_MONTH = BLOCKING_BASE.replace(
    "and (select count(*) from orders x",
    "and o.date_order_paid >= %(cohort_start)s and o.date_order_paid < %(cohort_end)s\n    and (select count(*) from orders x",
) + """
select date_trunc('month', paid_at)::date as paid_month, count(*) as paid,
  count(*) filter (where profile_at is not null) as profile_done,
  count(*) filter (where shipped_at is not null) as shipped
from b group by 1 order by 1
"""

# ---- date quality audit (diag.py, diag2.py) ------------------------------------------------------------------
DATE_COLUMNS = [
    ("orders", "date_order_paid"), ("orders", "activation_date"), ("orders", "allied_order_date"),
    ("shipments", "date_shipped"), ("shipments", "delivered_to_customer_date"),
    ("shipments", "delivered_to_facility1_date"), ("samples", "received_by_lab_date"),
    ("samples", "processed_by_lab_date"), ("resultvalues", "created_date"),
    ("resultvalues", "customer_viewed_date"),
]
def date_quality_sql(table: str, column: str) -> str:
    """How many dates fall on the single busiest day (bulk-stamping shows up as a high share)."""
    import re
    if not (re.fullmatch(r"[a-z_0-9]+", table) and re.fullmatch(r"[a-z_0-9]+", column)):
        raise ValueError("table and column must be plain lowercase identifiers")
    return f"""
select '{table}' as table_name, '{column}' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select {column}::date d, count(*) c from {table} where {column} is not null group by 1) t
"""


DATE_SANITY = f"""
select count(*) n,
  count(*) filter (where s.date_shipped < o.date_order_paid) shipped_before_paid,
  count(*) filter (where s.date_shipped < o.created_date) shipped_before_created,
  percentile_cont(0.5) within group (order by extract(epoch from (o.date_order_paid - o.created_date))/86400) med_paid_minus_created_days,
  percentile_cont(0.5) within group (order by extract(epoch from (s.date_shipped - o.created_date))/86400) med_shipped_minus_created_days
from orders o join shipments s on s.order_id=o.id where {NOT_REPLACEMENT}
"""


# ---- exploration and diagnostic queries (profile.py, diag.py to diag4.py, funnel.py) ----
NR = "coalesce(name,'') not ilike %(replacement_pattern)s"      # unaliased orders
NRO = "coalesce(o.name,'') not ilike %(replacement_pattern)s"   # orders aliased o

# ---- profile.py: first look at every table ------------------------------------------------------------
PROFILE = {
    "customers overview": """select count(*) n, count(date_of_birth) dob, count(subscribed_via) sub_via,
        count(shared_story_via) story_via, count(referral_hero_id) refhero, count(subscribed_url) sub_url,
        count(*) filter (where active) active, min(created_date) first_signup, max(created_date) last_signup
        from customers""",
    "subscribed_via": "select subscribed_via, count(*) n from customers group by 1 order by 2 desc limit 20",
    "shared_story_via": "select shared_story_via, count(*) n from customers group by 1 order by 2 desc limit 20",
    "profilecompletions": "select complete, count(*) n, count(distinct customer_id) customers from profilecompletions group by 1",
    "orders by sku/name": "select sku, name, package_unit, count(*) n from orders group by 1,2,3 order by 4 desc limit 25",
    "orders overview": """select count(*) n, count(distinct customer_id) customers, count(date_order_paid) paid,
        count(*) filter (where activated) activated, count(activation_date) act_date,
        count(*) filter (where suspended) suspended from orders""",
    "orders status": "select status, count(*) n from orders group by 1 order by 2 desc",
    "shipments status": "select status, return_status1, return_status2, count(*) n from shipments group by 1,2,3 order by 4 desc limit 25",
    "shipments overview": """select count(*) n, count(distinct order_id) orders, count(date_shipped) shipped,
        count(delivered_to_customer_date) delivered, count(shipped_to_facility1_date) ship_fac1,
        count(delivered_to_facility1_date) deliv_fac1, count(shipped_to_facility2_date) ship_fac2,
        count(delivered_to_facility2_date) deliv_fac2 from shipments""",
    "samples kind/status": "select kind, status, count(*) n from samples group by 1,2 order by 3 desc",
    "samples overview": """select count(*) n, count(distinct shipment_id) shipments, count(received_by_lab_date) received,
        count(processed_by_lab_date) processed, count(analyzed_by_adyn_date) analyzed from samples""",
    "resultvalues overview": """select count(*) n, count(dna_sample_id) dna, count(hormone_sample_id) horm,
        count(*) filter (where adyn_approved) adyn_ok, count(*) filter (where por_approved) por_ok,
        count(customer_viewed_date) viewed, count(*) filter (where suspended) suspended from resultvalues""",
    "link: orders with a shipment": "select count(*) n from orders o where exists (select 1 from shipments s where s.order_id=o.id)",
    "link: shipments with a sample": "select count(*) n from shipments s where exists (select 1 from samples m where m.shipment_id=s.id)",
    "link: results matching a sample": """select count(*) n from resultvalues r where exists
        (select 1 from samples m where m.id in (r.dna_sample_id, r.hormone_sample_id))""",
    "couponorders": "select sku, count(*) n, count(date_order_paid) paid, count(distinct customer_id) buyers from couponorders group by 1 order by 2 desc",
    "coupons_redeemers": """select count(*) n, count(distinct redeemer_id) redeemers,
        count(*) filter (where redeemer_id in (select customer_id from orders)) with_orders from coupons_redeemers""",
    "paymentissues": "select status, count(*) n from paymentissues group by 1 order by 2 desc",
    "shippingaddresses by state": "select state, count(*) n from shippingaddresses group by 1 order by 2 desc limit 15",
    "shippingaddresses coverage": "select count(*) n, count(distinct customer_id) customers from shippingaddresses",
}

# ---- diag.py, diag2.py, diag3.py, diag4.py, funnel.py diagnostics ---------------------------------------
DIAGNOSTICS = {
    "shipped orders: date sanity": f"""select count(*) n,
        count(*) filter (where s.date_shipped < o.date_order_paid) shipped_before_paid,
        count(*) filter (where s.date_shipped < o.created_date) shipped_before_created,
        percentile_cont(0.5) within group (order by extract(epoch from (o.date_order_paid - o.created_date))/86400) med_paid_minus_created_days,
        percentile_cont(0.5) within group (order by extract(epoch from (s.date_shipped - o.created_date))/86400) med_shipped_minus_created_days
        from orders o join shipments s on s.order_id=o.id where {NRO}""",
    "most common activation_date values": "select activation_date, count(*) n from orders where activation_date is not null group by 1 order by 2 desc limit 5",
    "most common date_order_paid days": "select date_order_paid::date d, count(*) n from orders group by 1 order by 2 desc limit 5",
    "most common facility1 delivery days": "select delivered_to_facility1_date::date d, count(*) n from shipments group by 1 order by 2 desc limit 5",
    "customer delivery vs facility1": """select count(*) n,
        count(*) filter (where delivered_to_facility1_date::date = delivered_to_customer_date::date) same_day,
        percentile_cont(0.5) within group (order by extract(epoch from (delivered_to_facility1_date - delivered_to_customer_date))/86400) med_days
        from shipments""",
    "orderstatuses transitions": "select old_status, new_status, count(*) n, min(created_date)::date first_seen, max(created_date)::date last_seen from orderstatuses group by 1,2 order by 3 desc",
    "shipmentstatuses transitions": "select status, return_status1, return_status2, count(*) n, min(created_date)::date first_seen, max(created_date)::date last_seen from shipmentstatuses group by 1,2,3 order by 4 desc",
    "non-replacement orders by year x status": f"select extract(year from o.created_date)::int yr, o.status, count(*) n from orders o where {NRO} group by 1,2 order by 1,2",
    "reserved orders by state": f"""select sa.state, count(*) n from orders o join shippingaddresses sa on sa.customer_id=o.customer_id
        where o.status=%(reserved_status)s and {NRO} group by 1 order by 2 desc limit 8""",
    "replacements vs originals": """select (coalesce(name,'') ilike %(replacement_pattern)s) is_replacement, count(*) orders,
        count(*) filter (where exists(select 1 from shipments s where s.order_id=o.id)) shipped from orders o group by 1""",
    "when is DOB / profile captured": """select exists(select 1 from orders o where o.customer_id=c.id and o.activated) has_activated_order,
        count(*) customers, count(date_of_birth) with_dob,
        count(*) filter (where exists(select 1 from profilecompletions p where p.customer_id=c.id)) with_profile
        from customers c group by 1""",
    "most common date_shipped days": "select date_shipped::date d, count(*) n from shipments group by 1 order by 2 desc limit 5",
    "most common delivered_to_customer days": "select delivered_to_customer_date::date d, count(*) n from shipments group by 1 order by 2 desc limit 5",
    "most common received_by_lab days": "select received_by_lab_date::date d, count(*) n from samples group by 1 order by 2 desc limit 5",
    "most common processed_by_lab days": "select processed_by_lab_date::date d, count(*) n from samples group by 1 order by 2 desc limit 5",
    "most common resultvalues created days": "select created_date::date d, count(*) n from resultvalues group by 1 order by 2 desc limit 5",
    "most common customer_viewed days": "select customer_viewed_date::date d, count(*) n from resultvalues where customer_viewed_date is not null group by 1 order by 2 desc limit 5",
    "shipped orders: when did kit leave Allied vs paid": f"""select count(*) n,
        percentile_cont(0.5) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400) med_days_paid_to_left_allied,
        count(*) filter (where os.created_date < o.date_order_paid) left_before_paid
        from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ')=%(shipped_status)s
        where {NRO}""",
    "orders per customer (non-replacement)": f"""select n_orders, count(*) customers, sum(n_reserved) reserved_orders from (
        select customer_id, count(*) n_orders, count(*) filter (where status=%(reserved_status)s) n_reserved
        from orders where {NR} group by 1) t group by 1 order by 1""",
    "reserved orders: customers who also bought gift coupons": f"""select count(*) reserved_orders,
        count(*) filter (where customer_id in (select customer_id from couponorders)) from_gift_buyers
        from orders where status=%(reserved_status)s and {NR}""",
    "reserved orders: have activation_code": f"""select (activation_code is not null) has_code, count(*) n from orders
        where status=%(reserved_status)s and {NR} group by 1""",
    "activated orders: shipped before activation_date?": """select count(*) n,
        count(*) filter (where os.created_date < o.activation_date) left_allied_before_activation
        from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ')=%(shipped_status)s
        where o.activated""",
    "replacement orders by paid year": "select extract(year from date_order_paid)::int yr, count(*) n from orders where name ilike %(replacement_pattern)s group by 1 order by 1",
    "customers by role": """select role, count(*) n,
        count(*) filter (where exists(select 1 from orders o where o.customer_id=c.id)) with_order
        from customers c group by 1 order by 1""",
    "bulk accounts: role": """select c.role, count(*) n from customers c
        where (select count(*) from orders o where o.customer_id=c.id) >= %(bulk_min)s group by 1""",
    "orders by buyer role x status": f"""select c.role, o.status, count(*) n from orders o
        join customers c on c.id=o.customer_id where {NRO} group by 1,2 order by 1,2""",
    "allied_order_date vs status": f"""select o.status, count(*) n, count(o.allied_order_date) has_allied_date,
        count(o.allied_order_number) has_allied_no from orders o where {NRO} group by 1""",
    "paid -> allied_order_date days": f"""select count(*) n,
        round(percentile_cont(0.5) within group (order by extract(epoch from (allied_order_date-date_order_paid))/86400)::numeric,2) p50,
        round(percentile_cont(0.9) within group (order by extract(epoch from (allied_order_date-date_order_paid))/86400)::numeric,2) p90
        from orders o where {NRO} and allied_order_date is not null and date_order_paid is not null""",
    "placed vs paid": f"""select count(*) n, count(date_order_placed) placed, count(date_order_paid) paid,
        count(*) filter (where date_order_placed is not null and date_order_paid is null) placed_not_paid
        from orders o where {NRO}""",
    "reserved: suspended / approved flags": f"""select status, coalesce(suspended,false) susp, coalesce(adyn_approved,false) adyn_ok,
        coalesce(por_approved,false) por_ok, count(*) n from orders o where {NRO} group by 1,2,3,4 order by 5 desc""",
    "giftee accounts: orders": """select count(*) giftees,
        count(*) filter (where exists(select 1 from orders o where o.customer_id=c.id)) with_order
        from customers c where role=6""",
    "return status by kit (current shipments)": "select return_status1 saliva, return_status2 blood, count(*) n from shipments group by 1,2",
    "return status by kit (latest history per shipment)": """select s1.return_status1 saliva, s1.return_status2 blood, count(*) n from (
        select distinct on (shipment_id) * from shipmentstatuses order by shipment_id, created_date desc) s1 group by 1,2 order by 3 desc""",
    "order status x forms (shipped vs not)": f"""select o.status, count(*) orders,
        count(*) filter (where exists(select 1 from profilecompletions p where p.customer_id=o.customer_id and p.complete)) profile_complete,
        count(*) filter (where exists(select 1 from customerintake i where i.customer_id=o.customer_id and i.completed_date is not null)) intake_done,
        count(*) filter (where exists(select 1 from medicalhistory m where m.customer_id=o.customer_id and m.completed_date is not null)) medhist_done,
        count(*) filter (where c.date_of_birth is not null) has_dob,
        count(*) filter (where o.por_approved) por_ok
        from orders o join customers c on c.id=o.customer_id
        where {NRO} and c.role = any(%(customer_roles)s)
          and (select count(*) from orders x where x.customer_id=c.id) < %(bulk_min)s
        group by 1 order by 2 desc""",
    "orders: status x activated x paid x shipment x coupon match": f"""select status, coalesce(activated,false) activated,
        (date_order_paid is not null) paid, exists(select 1 from shipments s where s.order_id = o.id) has_shipment,
        exists(select 1 from couponorders c where c.friendly_order_id = o.friendly_order_id
               or c.stripe_invoice_item_id = o.stripe_invoice_item_id) matches_coupon_order, count(*) n
        from orders o where {NR} group by 1,2,3,4,5 order by n desc""",
    "results: approved x viewed": """select coalesce(adyn_approved,false) approved, (customer_viewed_date is not null) viewed, count(*) n
        from resultvalues group by 1,2 order by 1,2""",
    "customers by signup year": """select extract(year from created_date)::int yr, count(*) signups, count(date_of_birth) with_dob,
        count(*) filter (where exists (select 1 from orders o where o.customer_id = c.id)) with_order
        from customers c group by 1 order by 1""",
    "customerintake types": "select intake_type, count(*) n, count(completed_date) completed from customerintake group by 1",
    "customerintake form keys (names only, no answers)": """select k as key, count(*) n from customerintake ci,
        jsonb_object_keys(case when jsonb_typeof(ci.intake_form) = 'object' then ci.intake_form else '{}'::jsonb end) k
        group by 1 order by 2 desc limit 40""",
    "are sample/result links time-consistent with the order?": f"""select count(distinct r.id) results,
        count(distinct r.id) filter (where r.created_date < o.date_order_paid) result_before_order_paid,
        count(distinct r.id) filter (where m.received_by_lab_date < o.date_order_paid) lab_received_before_order_paid
        from orders o join shipments s on s.order_id=o.id join samples m on m.shipment_id=s.id
        join resultvalues r on m.id in (r.dna_sample_id, r.hormone_sample_id) where {NRO}""",
    "reserved rate: gift buyers vs others": f"""select (customer_id in (select customer_id from couponorders)) gift_buyer, count(*) orders,
        count(*) filter (where status=%(reserved_status)s) reserved from orders where {NR} group by 1""",
}
