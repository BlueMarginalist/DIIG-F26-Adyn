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
  select o.id, o.customer_id, o.date_order_paid, o.status
  from orders o where coalesce(o.name,'') not ilike '%replacement%'
),
ord_c as (
  select customer_id, count(*) n_orders, min(date_order_paid) first_paid,
         count(*) filter (where status = 'reserved') n_reserved
  from ord group by 1
),
st as (
  select o.customer_id,
    min(os.created_date) filter (where replace(os.new_status,'_',' ') = 'allied reserved') sent_to_allied,
    min(os.created_date) filter (where replace(os.new_status,'_',' ') = 'left allied facility') shipped
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

df = run(SQL_CUSTOMERS)
DATES = ["created_date","first_paid","sent_to_allied","shipped","lab_received",
         "lab_processed","result_created","result_approved_date","result_viewed"]
for c in DATES:
    df[c] = pd.to_datetime(df[c])
df["age_at_signup"] = pd.to_numeric(df["age_at_signup"], errors="coerce")
df["n_orders"] = df["n_orders"].fillna(0).astype(int)
df["result_approved"] = df["result_approved"].fillna(False).astype(bool)

bulk = df[df["n_orders"] >= 10]
print(f"Excluded {len(bulk)} bulk accounts (>=10 orders each): orders per account = {sorted(bulk['n_orders'].tolist())}")
df = df[df["n_orders"] < 10].copy()
df.to_csv(os.path.join(OUT, "funnel_v2_customers.csv"), index=False)

# ---------- 1. Funnel (real dates only) ----------
STAGES = [
    ("Account created", df["created_date"].notna()),
    ("Paid order", df["first_paid"].notna()),
    ("Sent to Allied", df["sent_to_allied"].notna()),
    ("Kit shipped (left Allied)", df["shipped"].notna()),
    ("Sample received by lab", df["lab_received"].notna()),
    ("Result created", df["result_created"].notna()),
    ("Result approved", df["result_approved"]),
    ("Result viewed", df["result_viewed"].notna()),
]
base_paid = int(STAGES[1][1].sum())
rows, prev = [], None
for name, flag in STAGES:
    n = int(flag.sum())
    rows.append({"stage": name, "customers": n,
                 "pct_of_prev": round(100*n/prev, 1) if prev else None,
                 "pct_of_paid": round(100*n/base_paid, 1) if name != "Account created" else None,
                 "lost_vs_prev": (prev - n) if prev is not None else None})
    prev = n
f = pd.DataFrame(rows)
print("\n=== FUNNEL (unique customers; replacements and bulk accounts excluded) ===")
print(f.to_string(index=False))
worst = f.loc[f["lost_vs_prev"].astype(float).idxmax()]
print(f"\nLargest drop: into '{worst['stage']}' (lost {int(worst['lost_vs_prev'])})")
print("(A small rise vs the stage above just means a customer skipped a status step.)")

# ---------- 2. Time between stages ----------
PAIRS = [("created_date","first_paid"), ("first_paid","sent_to_allied"), ("sent_to_allied","shipped"),
         ("first_paid","shipped"), ("shipped","lab_received"), ("lab_processed","result_created"),
         ("result_created","result_approved_date"), ("result_approved_date","result_viewed"),
         ("result_created","result_viewed"), ("first_paid","result_viewed")]
gaps = []
for a, b in PAIRS:
    m = df[a].notna() & df[b].notna()
    d = (df.loc[m, b] - df.loc[m, a]).dt.total_seconds() / 86400
    gaps.append({"from": a, "to": b, "n": int(m.sum()),
                 "median_days": round(d.median(), 1) if len(d) else None,
                 "p25": round(d.quantile(.25), 1) if len(d) else None,
                 "p75": round(d.quantile(.75), 1) if len(d) else None,
                 "pct_negative": round(100*(d < 0).mean(), 1) if len(d) else None})
print("\n=== DAYS BETWEEN STAGES (lab dates are batch-level; pct_negative > 0 = dates disagree) ===")
print(pd.DataFrame(gaps).to_string(index=False))

# ---------- 3. Paid -> shipped: who ships? ----------
paid = df[df["first_paid"].notna()].copy()
paid["shipped_f"] = paid["shipped"].notna()
paid["paid_year"] = paid["first_paid"].dt.year
s = paid["state"].fillna("unknown")
paid["state_group"] = s.where(s.isin(s.value_counts().head(8).index), "Other")
paid["gift_redeemer_f"] = paid["gift_redeemer"].map({True: "redeemed gift code", False: "no"})
paid["gift_buyer_f"] = paid["bought_gift"].map({True: "bought a gift", False: "no"})
paid["age_group"] = (pd.cut(paid["age_at_signup"], [0, 24, 29, 34, 200],
                     labels=["<=24", "25-29", "30-34", "35+"]).astype(object).fillna("unknown"))

def ship_rate(col, title):
    g = paid.groupby(col).agg(paid_customers=("shipped_f", "size"), shipped=("shipped_f", "sum"))
    g["pct_shipped"] = (100*g["shipped"]/g["paid_customers"]).round(1)
    g["small_n"] = g["paid_customers"] < 20
    print(f"\n=== PAID -> SHIPPED BY {title} ===")
    print(g.to_string())

for col, title in [("paid_year", "PAID YEAR"), ("state_group", "STATE"),
                   ("gift_redeemer_f", "GIFT REDEEMER"), ("gift_buyer_f", "GIFT BUYER")]:
    ship_rate(col, title)

# ---------- 4. Shipped -> viewed: who completes? ----------
sh = paid[paid["shipped_f"]].copy()
sh["result_f"] = sh["result_created"].notna()
sh["viewed_f"] = sh["result_viewed"].notna()

def result_rate(col, title):
    g = sh.groupby(col).agg(shipped=("result_f", "size"), got_result=("result_f", "sum"),
                            approved=("result_approved", "sum"), viewed=("viewed_f", "sum"))
    g["pct_result"] = (100*g["got_result"]/g["shipped"]).round(1)
    g["pct_approved"] = (100*g["approved"]/g["shipped"]).round(1)
    g["pct_viewed"] = (100*g["viewed"]/g["shipped"]).round(1)
    g["small_n"] = g["shipped"] < 20
    print(f"\n=== SHIPPED -> RESULT/VIEWED BY {title} (shipped customers only) ===")
    print(g.to_string())

for col, title in [("paid_year", "PAID YEAR"), ("age_group", "AGE"), ("state_group", "STATE"),
                   ("gift_redeemer_f", "GIFT REDEEMER")]:
    result_rate(col, title)

# ---------- 5. Saliva vs blood: does each shipment have a sample row? ----------
SQL_KIT = """
select (coalesce(o.name,'') ilike '%replacement%') is_replacement, count(*) shipments,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV')) has_saliva,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV' and m.status='valid')) saliva_valid,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD')) has_blood,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD' and m.status='valid')) blood_valid
from shipments s join orders o on o.id = s.order_id group by 1 order by 1
"""
print("\n=== SALIVA vs BLOOD (per shipment; is_replacement False = original kit) ===")
print(run(SQL_KIT).to_string(index=False))

# ---------- 6. Order cohorts + diagnostics ----------
NR = "coalesce(name,'') not ilike '%replacement%'"
NRO = "coalesce(o.name,'') not ilike '%replacement%'"
DIAG = [
("order cohorts by paid year (non-replacement, all accounts)", f"""
select extract(year from date_order_paid)::int paid_year, count(*) orders,
  count(*) filter (where status='left allied facility') shipped,
  count(*) filter (where status='reserved') reserved
from orders where {NR} and date_order_paid is not null group by 1 order by 1"""),
("days from payment to leaving Allied", f"""
select count(*) n,
  round(percentile_cont(0.5) within group (order by d)::numeric,2) p50_days,
  round(percentile_cont(0.9) within group (order by d)::numeric,2) p90_days,
  round(max(d)::numeric,2) max_days
from (select extract(epoch from (os.created_date - o.date_order_paid))/86400 d
  from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ')='left allied facility'
  where {NRO} and o.date_order_paid is not null) t"""),
("reserved rate: gift buyers vs others", f"""
select (customer_id in (select customer_id from couponorders)) gift_buyer, count(*) orders,
  count(*) filter (where status='reserved') reserved
from orders where {NR} group by 1"""),
("are sample/result links time-consistent with the order?", f"""
select count(distinct r.id) results,
  count(distinct r.id) filter (where r.created_date < o.date_order_paid) result_before_order_paid,
  count(distinct r.id) filter (where m.received_by_lab_date < o.date_order_paid) lab_received_before_order_paid
from orders o join shipments s on s.order_id=o.id join samples m on m.shipment_id=s.id
join resultvalues r on m.id in (r.dna_sample_id, r.hormone_sample_id) where {NRO}"""),
("replacement orders by month", """
select date_trunc('month', date_order_paid)::date month, count(*) from orders
where name ilike '%replacement%' group by 1 order by 1"""),
("accounts with vs without an order: what are they?", """
select exists(select 1 from orders o where o.customer_id=c.id) has_order, count(*) n,
  count(*) filter (where v_code_used) verified, count(*) filter (where terms_confirmed) terms,
  count(*) filter (where age_confirmed) age_ok, count(*) filter (where stripe_customer_id is not null) has_stripe,
  count(*) filter (where hubspot_id is not null) has_hubspot,
  count(*) filter (where informed_consent_confirmed is not null) consent,
  count(*) filter (where exists(select 1 from shippingaddresses a where a.customer_id=c.id)) has_address,
  count(*) filter (where subscribed_via is not null) subscribed
from customers c group by 1"""),
]
for title, sql in DIAG:
    print(f"\n=== DIAGNOSTIC: {title} ===")
    try:
        print(run(sql).to_string(index=False))
    except Exception as e:
        conn.rollback()
        print("ERROR:", e)
conn.close()