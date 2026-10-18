import os, re, psycopg2

OUT = r"C:\Users\miche\OneDrive\Documents\DIIG_Project\data"
TABLES = ["customers", "profilecompletions", "orders", "orderstatuses",
          "shipments", "shipmentstatuses", "samples", "resultvalues",
          "couponorders", "paymentissues"]
# columns that directly identify a person; not needed for a funnel analysis
SKIP = re.compile(r"email|phone|first_?name|last_?name|full_?name|street|line1|line2|address1|address2", re.I)

conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"],
    port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"],
    user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"],
    connect_timeout=10,
)
cur = conn.cursor()

# 1) schema of every table -> schema.txt
cur.execute("""select table_schema, table_name, column_name, data_type
               from information_schema.columns
               where table_schema not in ('pg_catalog','information_schema')
               order by 1,2,ordinal_position""")
with open(os.path.join(OUT, "schema.txt"), "w") as f:
    for row in cur.fetchall():
        f.write(" | ".join(row) + "\n")
print("Wrote schema.txt")

# 2) row counts + 3) CSV export for project tables
for t in TABLES:
    cur.execute("""select column_name from information_schema.columns
                   where table_schema='public' and table_name=%s
                   order by ordinal_position""", (t,))
    cols = [c[0] for c in cur.fetchall()]
    if not cols:
        print(f"{t}: NOT FOUND"); continue
    keep = [c for c in cols if not SKIP.search(c)]
    dropped = [c for c in cols if SKIP.search(c)]
    cur.execute(f'select count(*) from public."{t}"')
    n = cur.fetchone()[0]
    collist = ", ".join(f'"{c}"' for c in keep)
    with open(os.path.join(OUT, f"{t}.csv"), "w", encoding="utf-8", newline="") as f:
        cur.copy_expert(f'COPY (select {collist} from public."{t}") TO STDOUT WITH CSV HEADER', f)
    print(f"{t}: {n} rows, {len(keep)} cols exported, skipped: {dropped}")
conn.close()
