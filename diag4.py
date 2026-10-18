import os, psycopg2
conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"], port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"], user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"], connect_timeout=10)
cur = conn.cursor()
NR = "coalesce(o.name,'') not ilike '%replacement%'"
cur.execute(f"""
select o.status,
  count(*) orders,
  count(*) filter (where exists(select 1 from profilecompletions p where p.customer_id=o.customer_id and p.complete)) profile_complete,
  count(*) filter (where exists(select 1 from customerintake i where i.customer_id=o.customer_id and i.completed_date is not null)) intake_done,
  count(*) filter (where exists(select 1 from medicalhistory m where m.customer_id=o.customer_id and m.completed_date is not null)) medhist_done,
  count(*) filter (where c.date_of_birth is not null) has_dob,
  count(*) filter (where o.por_approved) por_ok
from orders o join customers c on c.id=o.customer_id
where {NR} and c.role in (2,3) and (select count(*) from orders x where x.customer_id=c.id) < 10
group by 1 order by 2 desc""")
print([d[0] for d in cur.description])
for r in cur.fetchall(): print(r)
conn.close()