"""Checks for database switching and SQL-backed virtual-care coverage exports."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from adyn_dash import Config, DataStore, DemoBackend
from adyn_dash.database import PostgresBackend
from adyn_dash.build import build
from adyn_dash.modules.virtual_care import VirtualCare
from adyn_dash.lib.virtual_care.analysis import VirtualCareEDA


class ConnectionSwitchChecks(unittest.TestCase):
    def fake_driver(self):
        driver = types.ModuleType('psycopg')
        driver.connect = MagicMock()
        driver.sql = MagicMock()
        return driver

    def test_explicit_file_isolated_from_shell_and_preserves_dollar_password(self):
        driver = self.fake_driver()
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder)/'client.env'
            file.write_text('ADYN_POSTGRES_HOST=new.invalid\nADYN_POSTGRES_DB=newdb\nADYN_POSTGRES_USER=newuser\nADYN_POSTGRES_PASSWORD=${old}$literal\n')
            old = {f'ADYN_POSTGRES_{k}': v for k,v in
                   {'HOST':'old.invalid','DB':'old','USER':'old','PASSWORD':'old','PORT':'9999','SCHEMA':'oldschema'}.items()}
            with patch.dict(sys.modules, {'psycopg': driver}), patch.dict(os.environ, old):
                backend = PostgresBackend(env_file=file)
                self.assertEqual(os.environ['ADYN_POSTGRES_HOST'], 'old.invalid')
        kw = driver.connect.call_args.kwargs
        self.assertEqual((kw['host'], kw['dbname'], kw['user']), ('new.invalid','newdb','newuser'))
        self.assertEqual(kw['password'], '${old}$literal')
        self.assertEqual(kw['port'], '5432')
        backend.conn.cursor.assert_not_called()

    def test_incomplete_file_does_not_borrow_old_credentials(self):
        driver = self.fake_driver()
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'incomplete.env';file.write_text('ADYN_POSTGRES_HOST=new.invalid\n')
            with patch.dict(sys.modules, {'psycopg':driver}), patch.dict(os.environ, {'ADYN_POSTGRES_PASSWORD':'old'}):
                with self.assertRaisesRegex(ValueError, 'ADYN_POSTGRES_PASSWORD'):
                    PostgresBackend(env_file=file)
        driver.connect.assert_not_called()

    def test_missing_explicit_file_stops_before_connecting(self):
        driver=self.fake_driver()
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {'psycopg':driver}):
            with self.assertRaisesRegex(ValueError, 'does not exist'):
                PostgresBackend(env_file=Path(folder)/'absent.env')
        driver.connect.assert_not_called()

    def test_schema_file_and_explicit_override(self):
        driver=self.fake_driver()
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'client.env';file.write_text('ADYN_POSTGRES_HOST=h\nADYN_POSTGRES_DB=d\nADYN_POSTGRES_USER=u\nADYN_POSTGRES_PASSWORD=p\nADYN_POSTGRES_SCHEMA=file schema\n')
            with patch.dict(sys.modules, {'psycopg':driver}):
                PostgresBackend(env_file=file)
                driver.sql.Identifier.assert_called_with('file schema')
                PostgresBackend(Config(database_schema='explicit schema'), env_file=file)
                driver.sql.Identifier.assert_called_with('explicit schema')


class CoverageChecks(unittest.TestCase):
    def module(self, rows, viewers=('a','b','c','d')):
        module=object.__new__(VirtualCare)
        data=[]
        for i,(customer,status,outcome,created) in enumerate(rows):
            data.append(dict(id=i+1,customer_id=customer,status=status,appointment_outcome=outcome,
                             created_date=created,appointment_date='2024-02-02',sku='VC-SYNC-15CHRG',
                             patient_interaction_satisfaction=None))
        module.eda=VirtualCareEDA(pd.DataFrame(data))
        cohort=pd.DataFrame({'customer_id':list(viewers),'first_viewed_date':['2024-02-01']*len(viewers)})
        module.data=lambda name:cohort.copy()
        return module

    def test_statuses_deduplicate_customers_and_exclude_completed_customers(self):
        module=self.module([('a','cancelled',None,'2024-02-01'),('a','cancelled',None,'2024-02-01'),
                            ('a','scheduled',None,'2024-02-01'),('b',None,None,'2024-02-01'),
                            ('c','cancelled',None,'2024-02-01'),('c','completed','visit complete','2024-02-01'),
                            ('d','cancelled',None,None)])
        out=module.viewer_noncompletion_status().set_index('appointment_status')
        self.assertEqual(out.loc['cancelled','customers'],1)
        self.assertEqual(out.loc['scheduled','customers'],1)
        self.assertEqual(out.loc['Unknown status','customers'],1)
        self.assertTrue(out.report_viewers.eq(4).all())
        self.assertTrue(out.booked_without_observed_completion.eq(2).all())
        self.assertEqual(out.customers.sum(),3)  # deliberately overlapping status groups
        self.assertTrue(out.percent_report_viewers.eq(25).all())
        self.assertTrue(out.percent_noncompleters.eq(50).all())

    def test_no_qualifying_bookings_returns_empty_with_columns(self):
        module=self.module([('a','scheduled',None,'2024-01-01')])
        out=module.viewer_noncompletion_status()
        self.assertTrue(out.empty)
        self.assertIn('percent_report_viewers',out.columns)

    def test_empty_viewer_population_returns_empty(self):
        module=self.module([('a','scheduled',None,'2024-02-01')],viewers=())
        self.assertTrue(module.viewer_noncompletion_status().empty)

    def test_score_percentages_sum_to_100_for_observed_types(self):
        cfg=Config();module=VirtualCare(DataStore(DemoBackend([VirtualCare]),cfg),cfg)
        out=module.satisfaction()
        for _,group in out.groupby('visit_type'):
            if group.visits.sum():
                self.assertAlmostEqual(group.percent_of_type.sum(),100)
            else:
                self.assertTrue(group.percent_of_type.isna().all())

    def test_live_failure_does_not_use_synthetic_backend(self):
        with tempfile.TemporaryDirectory() as folder, patch('adyn_dash.build.PostgresBackend',side_effect=ValueError('missing settings')), patch('adyn_dash.build.DemoBackend') as demo:
            with self.assertRaisesRegex(ValueError,'missing settings'):
                build(['virtual_care'],out=folder)
            demo.assert_not_called()

    def test_manifest_exposes_filter_limit_and_new_chart(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest=build(['virtual_care'],out=folder,demo=True)
            self.assertFalse(manifest['global_filter_support']['age']['supported'])
            self.assertFalse(manifest['global_filter_support']['date_range']['supported'])
            entry=next(e for e in manifest['charts'] if e['id']=='virtual_care.viewer_noncompletion_status')
            self.assertEqual(entry['status'],'ok')
            self.assertIn('multiple',entry['export_metadata']['missing_value_note'])
            self.assertIn('global_filter_support',json.loads((Path(folder)/'manifest.json').read_text()))


if __name__ == '__main__':
    unittest.main()
