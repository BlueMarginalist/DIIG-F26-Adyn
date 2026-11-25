"""SQL join and denominator regressions for delivered-kit exports."""
import sqlite3
import unittest
from pathlib import Path
import pandas as pd
from adyn_dash import Config, DataStore, DemoBackend
from adyn_dash.modules.funnel import Funnel

class DeliveredKitChecks(unittest.TestCase):
    def query(self, shipments, events, samples):
        db=sqlite3.connect(':memory:')
        db.executescript('''create table orders(id integer,name text);
        insert into orders values(1,'kit'),(2,'Replacement kit');
        create table shipments(id integer,order_id integer);
        create table shipmentstatuses(shipment_id integer,status text,created_date text);
        create table samples(shipment_id integer,kind text,status text,received_by_lab_date text);''')
        db.executemany('insert into shipments values(?,?)',shipments)
        db.executemany('insert into shipmentstatuses values(?,?,?)',events)
        db.executemany('insert into samples values(?,?,?,?)',samples)
        sql=(Path(__file__).parents[1]/'adyn_dash/sources/funnel/delivered_kit_samples.sql').read_text()
        # Only dialect substitution; PostgreSQL/schema validation still needs staging.
        sql=sql.replace('ilike %(replacement_pattern)s',"like '%replacement%'")
        try:
            return pd.read_sql_query(sql,db)
        finally:
            db.close()

    def test_duplicate_events_and_samples_do_not_multiply_kits(self):
        d=self.query([(1,1)],[(1,'delivered','2024-01-01')]*3,
            [(1,'KIT-SLV','valid','2024-01-03')]*3+[(1,'KIT-BLD','valid','2024-01-04')]*2).iloc[0]
        self.assertEqual(tuple(d[c] for c in ('delivered_kits','two_logged','both_valid')),(1,1,1))

    def test_returns_validity_and_missing_delivery_are_distinct(self):
        d=self.query([(i,1) for i in range(1,6)],[(i,'delivered','2024-01-02') for i in (1,2,3,4)],
            [(2,'KIT-SLV','failed','2024-01-03'),(3,'KIT-SLV','valid','2024-01-03'),
             (3,'KIT-BLD','failed','2024-01-04'),(4,'KIT-SLV','valid','2024-01-01'),
             (4,'KIT-BLD','valid','2024-01-03'),(5,'KIT-SLV','valid','2024-01-03')]).iloc[0]
        self.assertEqual(tuple(d[c] for c in ('delivered_kits','delivery_not_logged','zero_logged',
            'one_logged','two_logged','invalid_timing','both_valid')),(4,1,1,1,1,1,1))

    def test_both_valid_never_combines_separate_shipments(self):
        d=self.query([(1,1),(2,1)],[(i,'delivered','2024-01-01') for i in (1,2)],
            [(1,'KIT-SLV','valid','2024-01-03'),(2,'KIT-BLD','valid','2024-01-03')]).iloc[0]
        self.assertEqual(d['both_valid'],0)
        self.assertEqual(d['one_logged'],2)

    def test_unrecognized_sample_types_are_not_counted(self):
        d=self.query([(1,1)],[(1,'delivered','2024-01-01')],[(1,'OTHER','valid','2024-01-03')]).iloc[0]
        self.assertEqual(d['zero_logged'],1)
        self.assertEqual(d['both_valid'],0)

    def test_original_and_replacement_denominators(self):
        d=self.query([(1,1),(2,1),(3,2)],[(i,'delivered','2024-01-01') for i in (1,2,3)],[])
        self.assertEqual(d['delivered_kits'].tolist(),[2,1])

    def test_export_totals_use_delivered_denominator(self):
        cfg=Config(); m=Funnel(DataStore(DemoBackend([Funnel]),cfg),cfg)
        for _,g in m.run('delivered_kit_returns').groupby('kit'):
            self.assertEqual(g['kits'].sum(),g['delivered_kits'].iloc[0])
            self.assertAlmostEqual(g['percent'].sum(),100)
        d=m.run('delivered_kit_both_valid').set_index('kit')
        self.assertEqual(d.loc['original','percent_both_valid'],65)
        self.assertEqual(d.loc['replacement','percent_both_valid'],50)

    def test_zero_denominator_is_unknown_not_zero(self):
        m=object.__new__(Funnel)
        m.data=lambda name:pd.DataFrame([dict(is_replacement=False,delivered_kits=0,
            delivery_not_logged=5,zero_logged=0,one_logged=0,two_logged=0,invalid_timing=0,both_valid=0)])
        self.assertTrue(m.delivered_kit_returns()['percent'].isna().all())
        self.assertTrue(m.delivered_kit_both_valid()['percent_both_valid'].isna().all())

if __name__=='__main__':
    unittest.main()
