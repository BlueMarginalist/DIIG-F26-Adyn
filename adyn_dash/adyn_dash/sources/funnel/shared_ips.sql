-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) as shared_ip_groups, sum(n) as orders_in_groups, sum(reserved) as reserved_in_groups from (
  select o.ip, count(*) n, count(*) filter (where o.status=%(reserved_status)s) reserved
  from orders o where coalesce(o.name,'') not ilike %(replacement_pattern)s and o.ip is not null group by 1 having count(*) >= %(shared_ip_min)s) t
