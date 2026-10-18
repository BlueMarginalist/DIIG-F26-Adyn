import os, sys, psycopg2

table = sys.argv[1]
conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"],
    port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"],
    user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"],
    connect_timeout=10,
)
with conn.cursor() as cur:
    cur.execute("""select column_name, data_type from information_schema.columns
                   where table_schema='public' and table_name=%s order by ordinal_position""", (table,))
    print("COLUMNS:")
    for c in cur.fetchall():
        print("  ", c)
    cur.execute(f'select count(*) from public."{table}"')
    print("ROW COUNT:", cur.fetchone()[0])
conn.close()