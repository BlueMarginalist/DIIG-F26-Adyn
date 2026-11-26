-- One shipment is one kit. Aggregate samples and delivery events before joining.
-- A lab receipt is evidence of a logged return, not necessarily a valid sample.
with delivery as (
  select shipment_id, min(created_date) as delivered_at
  from shipmentstatuses where status='delivered' group by shipment_id
), sample_flags as (
  select shipment_id,
    min(received_by_lab_date) filter (where kind='KIT-SLV') saliva_received,
    min(received_by_lab_date) filter (where kind='KIT-BLD') blood_received,
    max(case when kind='KIT-SLV' and status='valid' then 1 else 0 end) saliva_valid,
    max(case when kind='KIT-BLD' and status='valid' then 1 else 0 end) blood_valid
  from samples group by shipment_id
), kits as (
  select (coalesce(o.name,'') ilike %(replacement_pattern)s) is_replacement,
    d.delivered_at,
    case when f.saliva_received is not null then 1 else 0 end
      + case when f.blood_received is not null then 1 else 0 end returned_types,
    case when f.saliva_received < d.delivered_at or f.blood_received < d.delivered_at
      then 1 else 0 end invalid_timing,
    case when f.saliva_valid=1 and f.blood_valid=1 then 1 else 0 end both_valid
  from shipments s join orders o on o.id=s.order_id
  left join delivery d on d.shipment_id=s.id
  left join sample_flags f on f.shipment_id=s.id
)
select is_replacement,
  count(*) filter (where delivered_at is not null) delivered_kits,
  count(*) filter (where delivered_at is null) delivery_not_logged,
  count(*) filter (where delivered_at is not null and invalid_timing=0 and returned_types=0) zero_logged,
  count(*) filter (where delivered_at is not null and invalid_timing=0 and returned_types=1) one_logged,
  count(*) filter (where delivered_at is not null and invalid_timing=0 and returned_types=2) two_logged,
  count(*) filter (where delivered_at is not null and invalid_timing=1) invalid_timing,
  count(*) filter (where delivered_at is not null and both_valid=1) both_valid
from kits group by is_replacement order by is_replacement
