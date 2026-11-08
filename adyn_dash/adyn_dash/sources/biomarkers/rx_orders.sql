-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select customer_id, sku, date_order_placed
from rxorders
where sku like 'AD-BC-%' and sku not in ('AD-BC-EXTERNAL', 'AD-BC-FREE0000')
