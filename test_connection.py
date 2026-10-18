import os, psycopg2

conn = psycopg2.connect(
    host=os.environ["ADYN_POSTGRES_HOST"],
    port=os.environ["ADYN_POSTGRES_PORT"],
    dbname=os.environ["ADYN_POSTGRES_DB"],
    user=os.environ["ADYN_POSTGRES_USER"],
    password=os.environ["ADYN_POSTGRES_PASSWORD"],
    connect_timeout=10,
)
with conn.cursor() as cur:
    cur.execute("select version()")
    print(cur.fetchone())
    cur.execute("""
        select table_schema, table_name
        from information_schema.tables
        where table_schema not in ('pg_catalog', 'information_schema')
        order by 1, 2
    """)
    for row in cur.fetchall():
        print(row)
conn.close()