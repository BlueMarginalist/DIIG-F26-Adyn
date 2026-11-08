-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select (coalesce(o.name,'') ilike %(replacement_pattern)s) is_replacement, count(*) shipments,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV')) has_saliva,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-SLV' and m.status='valid')) saliva_valid,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD')) has_blood,
  count(*) filter (where exists(select 1 from samples m where m.shipment_id=s.id and m.kind='KIT-BLD' and m.status='valid')) blood_valid
from shipments s join orders o on o.id = s.order_id group by 1 order by 1
