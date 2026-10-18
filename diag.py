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

NR = "coalesce(o.name,'') not ilike '%replacement%'"
Q = [
("shipped orders: date sanity", f"""select count(*) n,
  count(*) filter (where s.date_shipped < o.date_order_paid) shipped_before_paid,
  count(*) filter (where s.date_shipped < o.created_date) shipped_before_created,
  percentile_cont(0.5) within group (order by extract(epoch from (o.date_order_paid - o.created_date))/86400) med_paid_minus_created_days,
  percentile_cont(0.5) within group (order by extract(epoch from (s.date_shipped - o.created_date))/86400) med_shipped_minus_created_days
  from orders o join shipments s on s.order_id=o.id where {NR}"""),
("most common activation_date values", "select activation_date, count(*) from orders where activation_date is not null group by 1 order by 2 desc limit 5"),
("most common date_order_paid days", "select date_order_paid::date, count(*) from orders group by 1 order by 2 desc limit 5"),
("most common facility1 delivery days", "select delivered_to_facility1_date::date, count(*) from shipments group by 1 order by 2 desc limit 5"),
("customer delivery vs facility1", """select count(*) n,
  count(*) filter (where delivered_to_facility1_date::date = delivered_to_customer_date::date) same_day,
  percentile_cont(0.5) within group (order by extract(epoch from (delivered_to_facility1_date - delivered_to_customer_date))/86400) med_days
  from shipments"""),
("orderstatuses transitions", "select old_status, new_status, count(*), min(created_date)::date, max(created_date)::date from orderstatuses group by 1,2 order by 3 desc"),
("shipmentstatuses transitions", "select status, return_status1, return_status2, count(*), min(created_date)::date, max(created_date)::date from shipmentstatuses group by 1,2,3 order by 4 desc"),
("non-replacement orders by year x status", f"select extract(year from o.created_date)::int yr, o.status, count(*) from orders o where {NR} group by 1,2 order by 1,2"),
("reserved orders by state", f"""select sa.state, count(*) from orders o join shippingaddresses sa on sa.customer_id=o.customer_id
  where o.status='reserved' and {NR} group by 1 order by 2 desc limit 8"""),
("replacements vs originals", """select (coalesce(name,'') ilike '%replacement%') is_replacement, count(*) orders,
  count(*) filter (where exists(select 1 from shipments s where s.order_id=o.id)) shipped from orders o group by 1"""),
("when is DOB / profile captured", """select exists(select 1 from orders o where o.customer_id=c.id and o.activated) has_activated_order,
  count(*) customers, count(date_of_birth) with_dob,
  count(*) filter (where exists(select 1 from profilecompletions p where p.customer_id=c.id)) with_profile
  from customers c group by 1"""),
]
for t, s in Q:
    q(t, s)
conn.close()