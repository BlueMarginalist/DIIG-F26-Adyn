"""Regression checks for integrated exploratory exports (no database required)."""
import json
import tempfile
from pathlib import Path
import unittest
from datetime import datetime, timezone

import pandas as pd

from adyn_dash import Config, DataStore, DemoBackend
from adyn_dash.build import build
from adyn_dash.modules.virtual_care import VirtualCare
from adyn_dash.lib.virtual_care.analysis import VirtualCareEDA
from adyn_dash.lib.virtual_care.demo import synthetic_data


class IntegrationChecks(unittest.TestCase):
    def module(self, cfg=None):
        cfg = cfg or Config()
        return VirtualCare(DataStore(DemoBackend([VirtualCare]), cfg), cfg)

    def test_inclusive_cutoff_and_config_validation(self):
        cfg = Config(vc_data_through='2026-03-04', vc_window_days=90)
        self.assertEqual(cfg.params()['vc_cutoff'], datetime(2026, 3, 5, tzinfo=timezone.utc))
        self.assertEqual(cfg.params()['vc_window'].days, 90)
        for kw in ({'vc_window_days': 0}, {'vc_small_group': 0}, {'vc_data_through': 'bad'}):
            with self.assertRaises(ValueError):
                Config(**kw)

    def test_all_factor_totals_agree(self):
        m = self.module()
        for method in (m.repeat_overall, m.repeat_by_age, m.repeat_by_rx, m.repeat_by_provider):
            table = method()
            self.assertEqual(table.customers.sum(), 10)
            self.assertEqual(table.repeat_customers.sum(), 4)
            self.assertFalse(table.cutoff_completeness_confirmed.any())
        self.assertEqual(m.repeat_overall().percent.item(), 40)

    def test_provider_ids_do_not_escape(self):
        table = self.module().run('repeat_by_provider')
        self.assertNotIn('demo-provider-a', table.to_json())
        self.assertIn('Provider 1', table.category.tolist())
        self.assertTrue(next(c for c in VirtualCare.charts() if c.name == 'repeat_by_provider').internal)

    def test_missing_categories_and_small_groups_stay_visible(self):
        m = self.module()
        age = m.repeat_by_age().set_index('category')
        self.assertTrue(age.loc['Unknown or invalid', 'small_group'])
        rx = m.repeat_by_rx().set_index('category')
        self.assertEqual(rx.loc['Unknown Rx timing', 'customers'], 1)

    def test_bad_counts_and_disagreeing_totals_raise(self):
        for mode in ('too_many', 'fractional', 'totals'):
            m = self.module()
            table = m.data('repeat_summary').copy()
            if mode == 'too_many': table.loc[0, 'repeat_customers'] = 99
            if mode == 'fractional':
                table['customers'] = table.customers.astype(float)
                table.loc[0, 'customers'] = 10.5
            if mode == 'totals': table.loc[0, 'customers'] = 11
            m.data = lambda name: table.copy()
            with self.assertRaises(ValueError):
                m.repeat_overall()

    def test_empty_cohort_exports_null_percent_with_explicit_cutoff(self):
        m = self.module(Config(vc_data_through='2026-03-04'))
        empty = m.data('repeat_summary').iloc[:0].copy()
        m.data = lambda name: empty.copy()
        out = m.repeat_overall()
        self.assertEqual(out.customers.item(), 0)
        self.assertTrue(out.percent.isna().all())

    def test_missing_live_cutoff_raises(self):
        m = self.module()
        empty = m.data('repeat_summary').iloc[:0].copy()
        m.data = lambda name: empty.copy()
        with self.assertRaisesRegex(ValueError, 'vc-data-through'):
            m.repeat_overall()

    def test_first_visit_ties_unknown_and_missing_dates(self):
        m = self.module()
        a, r = synthetic_data()
        # A starts with video, B starts with tied visits, C starts Unknown.
        a.loc[a.id.eq(7), 'appointment_date'] = a.loc[a.id.eq(6), 'appointment_date'].item()
        # E has a completed visit but no usable date.
        extra = a.iloc[[0]].copy()
        extra['id'], extra['customer_id'], extra['appointment_date'] = 999, 'demo-E', pd.NaT
        a = pd.concat([a, extra], ignore_index=True)
        m.eda = VirtualCareEDA(a, r)
        out = m.first_visit_types().set_index('first_type')
        self.assertEqual(out.loc['Video', 'customers'], 1)
        self.assertEqual(out.loc['Unknown', 'customers'], 1)
        self.assertEqual(out.loc['Tied earliest visits', 'customers'], 1)
        self.assertEqual(out.customers.sum(), 3)
        self.assertTrue(out.customers_without_dated_visits.eq(1).all())

    def test_full_virtual_care_demo_build(self):
        with tempfile.TemporaryDirectory() as folder:
            result = build(modules=['virtual_care'], out=folder, demo=True)
            self.assertEqual(len(result['charts']), 18)
            self.assertTrue(all(c['status'] == 'ok' for c in result['charts']))
            saved = json.loads((Path(folder) / 'manifest.json').read_text())
            for chart in saved['charts']:
                meta = chart['export_metadata']
                self.assertIsInstance(meta['entry_count'], int)
                self.assertGreaterEqual(meta['entry_count'], 0)
                self.assertTrue(meta['count_unit'])
                self.assertTrue(meta['missing_value_note'])
            overall = next(c for c in saved['charts'] if c['id'].endswith('.repeat_overall'))
            self.assertEqual(overall['export_metadata']['entry_count'], 10)

    def test_empty_export_keeps_count_and_missing_note(self):
        m = self.module()
        # No async visits: preserve empty-table semantics and describe the zero count.
        m.eda.completed = m.eda.completed.loc[~m.eda.completed.visit_type.eq('Async')].copy()
        out = m.run('video_to_async')
        self.assertTrue(out.empty)
        self.assertEqual(out.attrs['export_metadata']['entry_count'], 0)
        self.assertIn('empty table', out.attrs['export_metadata']['missing_value_note'])


if __name__ == '__main__':
    unittest.main()
