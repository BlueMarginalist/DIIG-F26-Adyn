-- Michelle Zuo, funnel_pkg/queries.py. Named parameters are filled from Config.params().
select count(*) as n_rows, count(distinct old_shipment_id) as distinct_old_shipments,
  count(reimbursed_date) as reimbursed from shipments_replacements
