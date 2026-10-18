import os, psycopg2, pandas as pd

OUT = r"C:\Users\miche\OneDrive\Documents\DIIG_Project\data"
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)

conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"], connect_timeout=10)
cur = conn.cursor()

def run(sql):
    cur.execute(sql)
    return pd.DataFrame(cur.fetchall(), columns=[d[0] for d in cur.description])

SQL_CUSTOMERS = """
with ord as (
  select id, customer_id, date_order_paid, activated, activation_date
  from orders where coalesce(name,'') not ilike '%replacement%'
),
ord_c as (
  select customer_id, count(*) n_orders, min(date_order_paid) first_paid,
         min(activation_date) filter (where activated) first_activated
  from ord group by 1
),
ship_c as (
  select o.customer_id, min(s.date_shipped) first_shipped,
         min(s.delivered_to_customer_date) first_delivered,
         min(least(s.delivered_to_facility1_date, s.delivered_to_facility2_date)) first_returned
  from ord o join shipments s on s.order_id = o.id group by 1
),
samp_c as (
  select o.customer_id, min(m.received_by_lab_date) lab_received,
         min(m.processed_by_lab_date) lab_processed
  from ord o join shipments s on s.order_id = o.id
  join samples m on m.shipment_id = s.id group by 1
),
res_c as (
  select o.customer_id, min(r.created_date) result_created,
         bool_or(coalesce(r.adyn_approved,false)) result_approved,
         min(r.modified_date) filter (where r.adyn_approved) result_approved_date,
         min(r.customer_viewed_date) result_viewed
  from ord o join shipments s on s.order_id = o.id
  join samples m on m.shipment_id = s.id
  join resultvalues r on m.id in (r.dna_sample_id, r.hormone_sample_id)
  group by 1
),
pc as (
  select customer_id, bool_or(complete) profile_complete,
         min(modified_date) filter (where complete) profile_complete_date
  from profilecompletions group by 1
)
select c.id as customer_id, c.created_date,
  extract(year from age(c.created_date, c.date_of_birth)) as age_at_signup,
  c.subscribed_via, sa.state,
  coalesce(pc.profile_complete,false) profile_complete, pc.profile_complete_date,
  exists(select 1 from coupons_redeemers cr where cr.redeemer_id = c.id) gift_redeemer,
  exists(select 1 from couponorders co where co.customer_id = c.id) bought_gift,
  exists(select 1 from paymentissues p where p.customer_id = c.id) payment_issue,
  oc.n_orders, oc.first_paid, oc.first_activated,
  sc.first_shipped, sc.first_delivered, sc.first_returned,
  mc.lab_received, mc.lab_processed,
  rc.result_created, rc.result_approved, rc.result_approved_date, rc.result_viewed
from customers c
left join ord_c oc on oc.customer_id = c.id
left join ship_c sc on sc.customer_id = c.id
left join samp_c mc on mc.customer_id = c.id
left join res_c rc on rc.customer_id = c.id
left join pc on pc.customer_id = c.id
left join shippingaddresses sa on sa.customer_id = c.id
"""

df = run(SQL_CUSTOMERS)
DATE_COLS = ["created_date","first_paid","first_activated","first_shipped","first_delivered",
             "first_returned","lab_received","lab_processed","result_created",
             "result_approved_date","result_viewed","profile_complete_date"]
for c in DATE_COLS:
    df[c] = pd.to_datetime(df[c])
df["age_at_signup"] = pd.to_numeric(df["age_at_signup"], errors="coerce")
df.to_csv(os.path.join(OUT, "funnel_customers.csv"), index=False)

# ---------- 1. Funnel ----------
STAGES = [
    ("Signed up", "created_date"), ("Paid order", "first_paid"),
    ("Kit shipped", "first_shipped"), ("Kit delivered", "first_delivered"),
    ("Kit activated", "first_activated"), ("Kit returned", "first_returned"),
    ("Lab processed", "lab_processed"), ("Result created", "result_created"),
    ("Result approved", "result_approved_date"), ("Result viewed", "result_viewed"),
]
rows, prev = [], None
for name, col in STAGES:
    n = int(df[col].notna().sum())
    rows.append({"stage": name, "customers": n,
                 "pct_of_prev": round(100*n/prev, 1) if prev else None,
                 "pct_of_signups": round(100*n/len(df), 1),
                 "lost_vs_prev": (prev - n) if prev is not None else None})
    prev = n
f = pd.DataFrame(rows)
print("\n=== FUNNEL (unique customers, replacement orders excluded) ===")
print(f.to_string(index=False))
worst = f.loc[f["lost_vs_prev"].astype(float).idxmax()]
print(f"\nLargest drop: into '{worst['stage']}' (lost {int(worst['lost_vs_prev'])} customers)")
print("(If a stage count RISES vs the one before it, my assumed stage order is wrong.)")

# ---------- 2. Time between stages ----------
gaps = []
for (an, a), (bn, b) in zip(STAGES, STAGES[1:]):
    m = df[a].notna() & df[b].notna()
    d = (df.loc[m, b] - df.loc[m, a]).dt.total_seconds() / 86400
    gaps.append({"from": an, "to": bn, "n": int(m.sum()),
                 "median_days": round(d.median(), 1) if len(d) else None,
                 "p25": round(d.quantile(.25), 1) if len(d) else None,
                 "p75": round(d.quantile(.75), 1) if len(d) else None,
                 "pct_negative": round(100*(d < 0).mean(), 1) if len(d) else None})
print("\n=== DAYS BETWEEN STAGES (pct_negative > 0 means the order is off for those rows) ===")
print(pd.DataFrame(gaps).to_string(index=False))

# ---------- 3. Saliva vs blood ----------
SQL_KIT = """
select count(*) shipments,
  count(*) filter (where slv > 0) slv, count(*) filter (where slv_valid > 0) slv_valid,
  count(*) filter (where bld > 0) bld, count(*) filter (where bld_valid > 0) bld_valid
from (select s.id,
        count(*) filter (where m.kind = 'KIT-SLV') slv,
        count(*) filter (where m.kind = 'KIT-SLV' and m.status = 'valid') slv_valid,
        count(*) filter (where m.kind = 'KIT-BLD') bld,
        count(*) filter (where m.kind = 'KIT-BLD' and m.status = 'valid') bld_valid
      from shipments s left join samples m on m.shipment_id = s.id group by s.id) t
"""
k = run(SQL_KIT).iloc[0]
tot = int(k["shipments"])
print("\n=== SALIVA vs BLOOD (per shipment) ===")
for label, a, b in [("Saliva (KIT-SLV)", "slv", "slv_valid"), ("Blood (KIT-BLD)", "bld", "bld_valid")]:
    print(f"{label}: {int(k[a])}/{tot} shipments got a sample to the lab ({100*k[a]/tot:.1f}%), "
          f"{int(k[b])}/{tot} valid ({100*k[b]/tot:.1f}%)")

# ---------- 4. Who completes? (people who paid for an order) ----------
o = df[df["first_paid"].notna()].copy()
o["returned"] = o["first_returned"].notna()
o["viewed"] = o["result_viewed"].notna()
o["age_group"] = (pd.cut(o["age_at_signup"], [0, 24, 29, 34, 200],
                  labels=["<=24", "25-29", "30-34", "35+"]).astype(object).fillna("unknown"))
st = o["state"].fillna("unknown")
top = st.value_counts().head(8).index
o["state_group"] = st.where(st.isin(top), "Other")
o["channel"] = o["subscribed_via"].fillna("not recorded")
o["gift"] = o["gift_redeemer"].map({True: "redeemed gift code", False: "self-purchase/other"})
o["profile"] = o["profile_complete"].map({True: "profile complete", False: "profile not complete"})

def breakdown(col, title):
    g = o.groupby(col).agg(paid_customers=("returned", "size"),
                           returned=("returned", "sum"), viewed=("viewed", "sum"))
    g["pct_returned"] = (100*g["returned"]/g["paid_customers"]).round(1)
    g["pct_viewed"] = (100*g["viewed"]/g["paid_customers"]).round(1)
    g["small_n"] = g["paid_customers"] < 20
    print(f"\n=== BY {title} ===")
    print(g.to_string())

for col, title in [("age_group", "AGE AT SIGNUP"), ("state_group", "STATE"),
                   ("channel", "ACQUISITION CHANNEL"), ("gift", "GIFT vs SELF"),
                   ("profile", "PROFILE COMPLETION")]:
    breakdown(col, title)

# ---------- 5. Diagnostics ----------
DIAG = [
("orders: status x activated x paid x has_shipment x matches_coupon (non-replacement)", """
select status, coalesce(activated,false) activated, (date_order_paid is not null) paid,
  exists(select 1 from shipments s where s.order_id = o.id) has_shipment,
  exists(select 1 from couponorders c where c.friendly_order_id = o.friendly_order_id
         or c.stripe_invoice_item_id = o.stripe_invoice_item_id) matches_coupon_order,
  count(*) n
from orders o where coalesce(name,'') not ilike '%replacement%'
group by 1,2,3,4,5 order by n desc"""),
("results: approved x viewed", """
select coalesce(adyn_approved,false) approved, (customer_viewed_date is not null) viewed, count(*) n
from resultvalues group by 1,2 order by 1,2"""),
("customers by signup year", """
select extract(year from created_date)::int yr, count(*) signups, count(date_of_birth) with_dob,
  count(*) filter (where exists (select 1 from orders o where o.customer_id = c.id)) with_order
from customers c group by 1 order by 1"""),
("customerintake types", "select intake_type, count(*) n, count(completed_date) completed from customerintake group by 1"),
("customerintake form keys (names only, no answers)", """
select k as key, count(*) n from customerintake ci,
  jsonb_object_keys(case when jsonb_typeof(ci.intake_form) = 'object' then ci.intake_form else '{}'::jsonb end) k
group by 1 order by 2 desc limit 40"""),
]
for title, sql in DIAG:
    print(f"\n=== DIAGNOSTIC: {title} ===")
    try:
        print(run(sql).to_string(index=False))
    except Exception as e:
        conn.rollback()
        print("ERROR:", e)
conn.close()