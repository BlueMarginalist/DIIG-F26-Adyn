-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select o.name, o.sku, count(*) n from orders o where coalesce(o.name,'') ilike %(replacement_pattern)s group by 1,2 order by 3 desc
