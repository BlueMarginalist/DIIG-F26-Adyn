import os, psycopg2
conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"], connect_timeout=10)
cur = conn.cursor()
def q(t, s):
    print("\n== " + t)
    try:
        cur.execute(s); print([d[0] for d in cur.description])
        for r in cur.fetchall(): print(r)
    except Exception as e:
        conn.rollback(); print("ERROR:", e)
NR = "coalesce(o.name,'') not ilike '%replacement%'"
for t, s in [
("customers by role", """select role, count(*) n,
  count(*) filter (where exists(select 1 from orders o where o.customer_id=c.id)) with_order
  from customers c group by 1 order by 1"""),
("bulk accounts: role", """select c.role, count(*) from customers c
  where (select count(*) from orders o where o.customer_id=c.id) >= 10 group by 1"""),
("orders by buyer role x status", f"""select c.role, o.status, count(*) from orders o
  join customers c on c.id=o.customer_id where {NR} group by 1,2 order by 1,2"""),
("allied_order_date vs status", f"""select o.status, count(*) n, count(o.allied_order_date) has_allied_date,
  count(o.allied_order_number) has_allied_no from orders o where {NR} group by 1"""),
("paid -> allied_order_date days", f"""select count(*) n,
  round(percentile_cont(0.5) within group (order by extract(epoch from (allied_order_date-date_order_paid))/86400)::numeric,2) p50,
  round(percentile_cont(0.9) within group (order by extract(epoch from (allied_order_date-date_order_paid))/86400)::numeric,2) p90
  from orders o where {NR} and allied_order_date is not null and date_order_paid is not null"""),
("placed vs paid", f"""select count(*) n, count(date_order_placed) placed, count(date_order_paid) paid,
  count(*) filter (where date_order_placed is not null and date_order_paid is null) placed_not_paid
  from orders o where {NR}"""),
("reserved: suspended / approved flags", f"""select status, coalesce(suspended,false) susp, coalesce(adyn_approved,false) adyn_ok,
  coalesce(por_approved,false) por_ok, count(*) from orders o where {NR} group by 1,2,3,4 order by 5 desc"""),
("giftee accounts: orders", """select count(*) giftees,
  count(*) filter (where exists(select 1 from orders o where o.customer_id=c.id)) with_order
  from customers c where role=6"""),
("return status by kit (current shipments)", """select return_status1 saliva, return_status2 blood, count(*) from shipments group by 1,2"""),
("return status by kit (latest history per shipment)", """select s1.return_status1 saliva, s1.return_status2 blood, count(*) from (
  select distinct on (shipment_id) * from shipmentstatuses order by shipment_id, created_date desc) s1 group by 1,2 order by 3 desc"""),
("sample status by kind", "select kind, status, count(*) from samples group by 1,2 order by 1,3 desc"),
]:
    q(t, s)
conn.close()