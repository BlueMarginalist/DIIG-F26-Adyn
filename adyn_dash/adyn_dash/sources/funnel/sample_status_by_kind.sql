-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select kind, status, count(*) n from samples group by 1,2 order by 1,3 desc
