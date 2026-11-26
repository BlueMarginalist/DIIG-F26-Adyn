-- Shihyun Kim, eda_biomarker_pkg/queries.py. Postgres-specific JSON operators (::jsonb, #>>) and DISTINCT ON.
select o.customer_id, sa.id as sample_id, sa.kind, sa.status, sa.received_by_lab_date
from samples sa
join shipments sh on sh.id = sa.shipment_id
join orders o on o.id = sh.order_id
