"""Regression checks for combining cleanup safeguards with newer virtual-care exports."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

import pandas as pd

from adyn_dash import Config
from adyn_dash.build import main, to_records
from adyn_dash.metrics import SKU_TYPES


class MergeChecks(unittest.TestCase):
    def test_both_configuration_validations_remain_active(self):
        for settings in ({'connect_timeout': 0}, {'small_n': 0},
                         {'vc_window_days': 0}, {'vc_small_group': 0},
                         {'vc_data_through': 'bad'}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                Config(**settings)

    def test_cli_preserves_schema_override_and_repeat_flags_without_as_of(self):
        with patch('adyn_dash.build.build', return_value={'charts': []}) as build:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--demo', '--schema', 'client schema',
                                       '--sql-override-dir', 'custom_queries',
                                       '--vc-data-through', '2026-03-04',
                                       '--vc-window-days', '60']), 0)
        cfg = build.call_args.args[4]
        self.assertIsNone(cfg.as_of)
        self.assertEqual(cfg.database_schema, 'client schema')
        self.assertEqual(cfg.sql_override_dir, 'custom_queries')
        self.assertEqual(cfg.params()['vc_window'].days, 60)
        self.assertEqual(cfg.params()['vc_cutoff'].date(), date(2026, 3, 5))

    def test_legacy_metric_import_uses_shared_definitions(self):
        from adyn_dash.lib.virtual_care.metrics import SKU_TYPES as legacy
        self.assertIs(legacy, SKU_TYPES)

    def test_calendar_date_exports_as_iso_string(self):
        result = to_records(pd.DataFrame({'day': [date(2026, 3, 4)]}))
        self.assertEqual(json.loads(json.dumps(result)), [{'day': '2026-03-04'}])


if __name__ == '__main__':
    unittest.main()
