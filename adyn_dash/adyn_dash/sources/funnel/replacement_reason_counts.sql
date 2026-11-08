-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) as total,
  count(*) filter (where reason ilike %(placeholder_like_pattern)s
                   or lower(reason) = any(%(placeholder_reasons)s)) as placeholder_like,
  count(*) filter (where reason ilike any(%(structured_prefixes)s)) as structured_real
from shipments_replacements
