-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) shipments,
  count(*) filter (where out_delivered is not null) delivered_to_customer_logged,
  count(*) filter (where ret1_delivered is not null) saliva_return_logged,
  count(*) filter (where ret2_delivered is not null) blood_return_logged,
  round(percentile_cont(0.5) within group (order by extract(epoch from (ret1_delivered-out_delivered))/86400)::numeric,1) med_days_saliva_back,
  round(percentile_cont(0.5) within group (order by extract(epoch from (ret2_delivered-out_delivered))/86400)::numeric,1) med_days_blood_back,
  round(percentile_cont(0.9) within group (order by extract(epoch from (ret2_delivered-out_delivered))/86400)::numeric,1) p90_days_blood_back
from (select shipment_id,
    min(created_date) filter (where status='delivered') out_delivered,
    min(created_date) filter (where return_status1='delivered') ret1_delivered,
    min(created_date) filter (where return_status2='delivered') ret2_delivered
  from shipmentstatuses group by 1) t
