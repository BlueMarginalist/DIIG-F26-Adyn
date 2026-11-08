-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) non_replacement_orders, count(*) filter (where o.status=%(reserved_status)s) reserved
from orders o where coalesce(o.name,'') not ilike %(replacement_pattern)s
