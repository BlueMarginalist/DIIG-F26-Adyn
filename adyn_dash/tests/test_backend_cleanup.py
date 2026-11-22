"""No-database regression checks for missing data, isolation and centralized rules."""
import json
import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

from adyn_dash import Config, DataStore, DemoBackend, Source
from adyn_dash.build import build
from adyn_dash.metrics import CONFIG_DEFAULTS, METRIC_DEFINITIONS, PRODUCTS, SKU_TYPES
from adyn_dash.modules import ALL_MODULES
from adyn_dash.modules.virtual_care import VirtualCare
from adyn_dash.source import SourceUnavailable


class BackendChecks(unittest.TestCase):
    def test_shared_rules_preserve_defaults_and_public_imports(self):
        from adyn_dash.lib.virtual_care import clean as vc
        from adyn_dash.lib.biomarkers import clean as bio
        self.assertIs(vc.SKU_TYPES, SKU_TYPES)
        self.assertIs(bio.PRODUCTS, PRODUCTS)
        self.assertEqual(Config().small_n, CONFIG_DEFAULTS['small_n'])
        self.assertEqual(Config().bulk_account_min_orders, 10)
        for value in METRIC_DEFINITIONS.values():
            for key in ('owner', 'definition', 'rule', 'caveats'):
                self.assertTrue(value[key])

    def test_empty_source_is_cached_and_refresh_retries(self):
        class Backend:
            calls = 0
            def fetch(self, source, cfg):
                self.calls += 1
                return pd.DataFrame(columns=['n'])
        backend = Backend()
        store, source = DataStore(backend), Source('toy', 'empty', ('n',))
        for _ in range(2):
            with self.assertRaises(SourceUnavailable): store.get(source)
        self.assertEqual(backend.calls, 1)
        store.refresh()
        with self.assertRaises(SourceUnavailable): store.get(source)
        self.assertEqual(backend.calls, 2)

    def test_bad_columns_are_errors_even_on_empty_input(self):
        class Backend:
            def fetch(self, source, cfg): return pd.DataFrame(columns=['wrong'])
        with self.assertRaisesRegex(ValueError, 'missing columns'):
            DataStore(Backend()).get(Source('toy', 'x', ('n',)))

    def test_zero_aggregate_is_valid_data(self):
        class Backend:
            def fetch(self, source, cfg): return pd.DataFrame({'n': [0]})
        self.assertEqual(DataStore(Backend()).get(Source('toy', 'x')).n.item(), 0)

    def test_missing_reports_do_not_block_visit_only_charts(self):
        class Backend(DemoBackend):
            def fetch(self, source, cfg):
                if source.name == 'reports': raise SourceUnavailable(source.key, 'missing_relation')
                return super().fetch(source, cfg)
        with tempfile.TemporaryDirectory() as folder:
            with patch('adyn_dash.build.PostgresBackend', return_value=Backend([VirtualCare])):
                result = build(['virtual_care'], out=folder)
            states = {c['id'].split('.')[-1]: c for c in result['charts']}
            self.assertEqual(states['report_waits']['status'], 'empty')
            self.assertEqual(states['report_waits']['reason'], 'missing_relation')
            self.assertEqual(states['monthly_visits']['status'], 'ok')
            self.assertEqual(states['visit_frequency']['status'], 'ok')

    def test_all_empty_sources_make_empty_states(self):
        class Backend(DemoBackend):
            def fetch(self, source, cfg): return super().fetch(source, cfg).iloc[:0]
        with tempfile.TemporaryDirectory() as folder:
            with patch('adyn_dash.build.PostgresBackend', return_value=Backend(ALL_MODULES.values())):
                result = build(out=folder)
            self.assertEqual(len(result['charts']), sum(len(m.charts()) for m in ALL_MODULES.values()))
            self.assertTrue(all(c['status'] == 'empty' for c in result['charts']))
            for entry in result['charts']:
                self.assertEqual(json.loads((Path(folder)/entry['file']).read_text()), [])

    def test_missing_data_replaces_stale_chart_files(self):
        class Backend:
            def fetch(self, source, cfg): raise SourceUnavailable(source.key, 'missing_relation')
            def close(self): pass
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'virtual_care/monthly_visits.json'
            path.parent.mkdir(parents=True); path.write_text('[{"old":99}]')
            with patch('adyn_dash.build.PostgresBackend', return_value=Backend()):
                build(['virtual_care'], out=folder)
            self.assertEqual(json.loads(path.read_text()), [])

    def test_programming_errors_remain_errors(self):
        def broken(self):
            raise RuntimeError('broken analysis')
        broken._chart = VirtualCare.monthly_visits._chart
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(VirtualCare, 'monthly_visits', broken):
                result = build(['virtual_care'], out=folder, demo=True)
            entry = next(c for c in result['charts'] if c['id'].endswith('.monthly_visits'))
            self.assertEqual(entry['status'], 'error')
            self.assertIn('broken analysis', entry['error'])

    def test_postgres_missing_relation_is_not_a_permission_error(self):
        from adyn_dash.database import PostgresBackend
        class MissingRelation(Exception): pass
        errors = types.ModuleType('psycopg.errors')
        errors.UndefinedTable = MissingRelation
        psycopg = types.ModuleType('psycopg')
        psycopg.errors = errors
        backend = object.__new__(PostgresBackend)
        backend.conn = MagicMock()
        cursor = backend.conn.cursor.return_value.__enter__.return_value
        source = Source('virtual_care', 'appointments')
        with patch.dict(sys.modules, {'psycopg': psycopg, 'psycopg.errors': errors}):
            cursor.execute.side_effect = MissingRelation()
            with self.assertRaises(SourceUnavailable) as caught:
                backend.fetch(source, Config())
            self.assertEqual(caught.exception.reason, 'missing_relation')
            cursor.execute.side_effect = PermissionError('access denied')
            with self.assertRaises(PermissionError): backend.fetch(source, Config())

    def test_connection_uses_readonly_and_central_credentials(self):
        from adyn_dash.database import PostgresBackend
        psycopg = types.ModuleType('psycopg')
        psycopg.connect = MagicMock()
        env = {f'ADYN_POSTGRES_{k}': v for k, v in
               dict(HOST='host.invalid', DB='scratch', USER='reader', PASSWORD='fake').items()}
        with patch.dict(sys.modules, {'psycopg': psycopg}), patch.dict('os.environ', env, clear=True):
            backend = PostgresBackend()
        options = psycopg.connect.call_args.kwargs
        self.assertIn('default_transaction_read_only=on', options['options'])
        self.assertEqual(options['host'], 'host.invalid')
        self.assertTrue(backend.conn.autocommit)

    def test_configured_schema_and_optional_file(self):
        with patch.dict('os.environ', {'ADYN_POSTGRES_SCHEMA': 'client schema'}):
            self.assertEqual(Config().connection_schema, 'client schema')
            self.assertEqual(Config(database_schema='override').connection_schema, 'override')


if __name__ == '__main__': unittest.main()
