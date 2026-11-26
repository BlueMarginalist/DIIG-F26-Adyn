-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) n, round(percentile_cont(0.25) within group (order by extract(epoch from (a.approved_at - rv.created_date))/86400)::numeric, 1) p25, round(percentile_cont(0.5) within group (order by extract(epoch from (a.approved_at - rv.created_date))/86400)::numeric, 1) p50, round(percentile_cont(0.75) within group (order by extract(epoch from (a.approved_at - rv.created_date))/86400)::numeric, 1) p75, round(percentile_cont(0.9) within group (order by extract(epoch from (a.approved_at - rv.created_date))/86400)::numeric, 1) p90
from resultvalues rv
join (select result_values_id, min(created_date) approved_at from resultvalueshistory
      where adyn_approved group by 1) a on a.result_values_id = rv.id
