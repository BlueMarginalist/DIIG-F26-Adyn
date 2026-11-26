-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select m.kind, coalesce(m.status,'(blank)') status, count(*) n from shipments_replacements r
join samples m on m.shipment_id = r.old_shipment_id group by 1,2 order by 3 desc
