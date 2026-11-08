-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select n_rep, count(*) customers from (
  select o.customer_id, count(*) n_rep from orders o where coalesce(o.name,'') ilike %(replacement_pattern)s group by 1) t
group by 1 order by 1
