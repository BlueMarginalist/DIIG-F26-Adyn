import os, psycopg2
conn = psycopg2.connect(host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"], connect_timeout=10)
cur = conn.cursor()
def q(title, sql):
    print("\n== " + title)
    try:
        cur.execute(sql); print([d[0] for d in cur.description])
        for r in cur.fetchall(): print(r)
    except Exception as e:
        conn.rollback(); print("ERROR:", e)

NOTREP = "coalesce(o.name,'') not ilike '%replacement%'"
q("1b (fixed). email domains with 5+ buyers (domain only)",
  f"""select split_part(lower(c.email),'@',2) as email_domain, count(distinct c.id) as buyers, count(o.id) as orders,
      count(o.id) filter (where o.status='reserved') as reserved,
      count(o.id) filter (where o.status='left allied facility') as shipped
    from customers c join orders o on o.customer_id=c.id where {NOTREP}
    group by 1 having count(distinct c.id) >= 5 order by 3 desc limit 15""")
q("2c (fixed). replacement table totals",
  """select count(*) as n_rows, count(distinct old_shipment_id) as distinct_old_shipments,
      count(reimbursed_date) as reimbursed from shipments_replacements""")
q("2b2. how many replacement reasons look like placeholder/test text (counts only)",
  """select count(*) as total,
      count(*) filter (where reason ilike '%test%' or lower(reason) in ('some reason','reason','new reason','reason for replacement')) as placeholder_like,
      count(*) filter (where reason ilike 'Lab reported%' or reason ilike 'Mail:%' or reason ilike 'Customer reported%') as structured_real
    from shipments_replacements""")
q("4g. 2023 cohort by paid month: paid, profile complete, shipped (counts only)",
  f"""with b as (
      select o.id, date_trunc('month', o.date_order_paid)::date as m,
        exists(select 1 from profilecompletions p where p.customer_id=o.customer_id and p.complete) as prof,
        exists(select 1 from orderstatuses os where os.order_id=o.id and replace(os.new_status,'_',' ')='left allied facility') as shp
      from orders o join customers c on c.id=o.customer_id
      where {NOTREP} and o.date_order_paid >= '2023-01-01' and o.date_order_paid < '2024-01-01'
        and c.role in (2,3) and (select count(*) from orders x where x.customer_id=c.id) < 10)
    select m, count(*) as paid, count(*) filter (where prof) as profile_done, count(*) filter (where shp) as shipped
    from b group by 1 order by 1""")
conn.close()
