-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select left(coalesce(reason,'(blank)'),60) reason, count(*) n from shipments_replacements
group by 1 having count(*) >= %(reason_min_count)s order by 2 desc limit 20
