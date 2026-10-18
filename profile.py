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

Q = [
("customers overview", """select count(*) n, count(date_of_birth) dob, count(subscribed_via) sub_via,
    count(shared_story_via) story_via, count(referral_hero_id) refhero, count(subscribed_url) sub_url,
    count(*) filter (where active) active, min(created_date) first_signup, max(created_date) last_signup
    from customers"""),
("subscribed_via", "select subscribed_via, count(*) from customers group by 1 order by 2 desc limit 20"),
("shared_story_via", "select shared_story_via, count(*) from customers group by 1 order by 2 desc limit 20"),
("profilecompletions", "select complete, count(*), count(distinct customer_id) from profilecompletions group by 1"),
("orders by sku/name", "select sku, name, package_unit, count(*) from orders group by 1,2,3 order by 4 desc limit 25"),
("orders overview", """select count(*) n, count(distinct customer_id) customers, count(date_order_paid) paid,
    count(*) filter (where activated) activated, count(activation_date) act_date,
    count(*) filter (where suspended) suspended from orders"""),
("orders status", "select status, count(*) from orders group by 1 order by 2 desc"),
("shipments status", "select status, return_status1, return_status2, count(*) from shipments group by 1,2,3 order by 4 desc limit 25"),
("shipments overview", """select count(*) n, count(distinct order_id) orders, count(date_shipped) shipped,
    count(delivered_to_customer_date) delivered, count(shipped_to_facility1_date) ship_fac1,
    count(delivered_to_facility1_date) deliv_fac1, count(shipped_to_facility2_date) ship_fac2,
    count(delivered_to_facility2_date) deliv_fac2 from shipments"""),
("samples kind/status", "select kind, status, count(*) from samples group by 1,2 order by 3 desc"),
("samples overview", """select count(*) n, count(distinct shipment_id) shipments, count(received_by_lab_date) received,
    count(processed_by_lab_date) processed, count(analyzed_by_adyn_date) analyzed from samples"""),
("resultvalues overview", """select count(*) n, count(dna_sample_id) dna, count(hormone_sample_id) horm,
    count(*) filter (where adyn_approved) adyn_ok, count(*) filter (where por_approved) por_ok,
    count(customer_viewed_date) viewed, count(*) filter (where suspended) suspended from resultvalues"""),
("link: orders with a shipment", "select count(*) from orders o where exists (select 1 from shipments s where s.order_id=o.id)"),
("link: shipments with a sample", "select count(*) from shipments s where exists (select 1 from samples m where m.shipment_id=s.id)"),
("link: results matching a sample", """select count(*) from resultvalues r where exists
    (select 1 from samples m where m.id in (r.dna_sample_id, r.hormone_sample_id))"""),
("couponorders", "select sku, count(*), count(date_order_paid) paid, count(distinct customer_id) buyers from couponorders group by 1 order by 2 desc"),
("coupons_redeemers", """select count(*) n, count(distinct redeemer_id) redeemers,
    count(*) filter (where redeemer_id in (select customer_id from orders)) with_orders from coupons_redeemers"""),
("paymentissues", "select status, count(*) from paymentissues group by 1 order by 2 desc"),
("shippingaddresses by state", "select state, count(*) from shippingaddresses group by 1 order by 2 desc limit 15"),
("shippingaddresses coverage", "select count(*) n, count(distinct customer_id) customers from shippingaddresses"),
]
for t, s in Q:
    q(t, s)
conn.close()