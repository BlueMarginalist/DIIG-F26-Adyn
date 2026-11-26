-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select 'orders' as table_name, 'date_order_paid' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select date_order_paid::date d, count(*) c from orders where date_order_paid is not null group by 1) t
union all
select 'orders' as table_name, 'activation_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select activation_date::date d, count(*) c from orders where activation_date is not null group by 1) t
union all
select 'orders' as table_name, 'allied_order_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select allied_order_date::date d, count(*) c from orders where allied_order_date is not null group by 1) t
union all
select 'shipments' as table_name, 'date_shipped' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select date_shipped::date d, count(*) c from shipments where date_shipped is not null group by 1) t
union all
select 'shipments' as table_name, 'delivered_to_customer_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select delivered_to_customer_date::date d, count(*) c from shipments where delivered_to_customer_date is not null group by 1) t
union all
select 'shipments' as table_name, 'delivered_to_facility1_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select delivered_to_facility1_date::date d, count(*) c from shipments where delivered_to_facility1_date is not null group by 1) t
union all
select 'samples' as table_name, 'received_by_lab_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select received_by_lab_date::date d, count(*) c from samples where received_by_lab_date is not null group by 1) t
union all
select 'samples' as table_name, 'processed_by_lab_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select processed_by_lab_date::date d, count(*) c from samples where processed_by_lab_date is not null group by 1) t
union all
select 'resultvalues' as table_name, 'created_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select created_date::date d, count(*) c from resultvalues where created_date is not null group by 1) t
union all
select 'resultvalues' as table_name, 'customer_viewed_date' as column_name,
  coalesce(sum(c),0)::int as n_dates, coalesce(max(c),0)::int as n_on_busiest_day,
  count(d)::int as distinct_days
from (select customer_viewed_date::date d, count(*) c from resultvalues where customer_viewed_date is not null group by 1) t
