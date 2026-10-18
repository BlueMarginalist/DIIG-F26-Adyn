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

NR = "coalesce(name,'') not ilike '%replacement%'"
Q = [
("most common date_shipped days", "select date_shipped::date, count(*) from shipments group by 1 order by 2 desc limit 5"),
("most common delivered_to_customer days", "select delivered_to_customer_date::date, count(*) from shipments group by 1 order by 2 desc limit 5"),
("most common received_by_lab days", "select received_by_lab_date::date, count(*) from samples group by 1 order by 2 desc limit 5"),
("most common processed_by_lab days", "select processed_by_lab_date::date, count(*) from samples group by 1 order by 2 desc limit 5"),
("most common resultvalues created days", "select created_date::date, count(*) from resultvalues group by 1 order by 2 desc limit 5"),
("most common customer_viewed days", "select customer_viewed_date::date, count(*) from resultvalues where customer_viewed_date is not null group by 1 order by 2 desc limit 5"),
("shipped orders: when did kit leave Allied vs paid", f"""select count(*) n,
  percentile_cont(0.5) within group (order by extract(epoch from (os.created_date - o.date_order_paid))/86400) med_days_paid_to_left_allied,
  count(*) filter (where os.created_date < o.date_order_paid) left_before_paid
  from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ')='left allied facility'
  where {NR}"""),
("orders per customer (non-replacement)", f"""select n_orders, count(*) customers, sum(n_reserved) reserved_orders from (
  select customer_id, count(*) n_orders, count(*) filter (where status='reserved') n_reserved
  from orders where {NR} group by 1) t group by 1 order by 1"""),
("reserved orders: customers who also bought gift coupons", f"""select count(*) reserved_orders,
  count(*) filter (where customer_id in (select customer_id from couponorders)) from_gift_buyers
  from orders where status='reserved' and {NR}"""),
("reserved orders: have activation_code", f"""select (activation_code is not null) has_code, count(*) from orders
  where status='reserved' and {NR} group by 1"""),
("activated orders: shipped before activation_date?", """select count(*) n,
  count(*) filter (where os.created_date < o.activation_date) left_allied_before_activation
  from orders o join orderstatuses os on os.order_id=o.id and replace(os.new_status,'_',' ')='left allied facility'
  where o.activated"""),
("replacement orders by paid year", """select extract(year from date_order_paid)::int yr, count(*) from orders
  where name ilike '%replacement%' group by 1 order by 1"""),
]
for t, s in Q:
    q(t, s)
conn.close()