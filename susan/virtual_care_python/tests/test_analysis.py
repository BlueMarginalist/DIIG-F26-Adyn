import unittest
import pandas as pd
from virtual_care_pkg import VirtualCareEDA, VirtualCarePlots, VirtualCareData
from virtual_care_pkg.demo import synthetic_data

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.a, self.r = synthetic_data()
        self.e = VirtualCareEDA(self.a, self.r)

    def test_spans_and_gaps(self):
        counts = self.e.visit_counts()
        row = counts.loc[counts.customer_id.eq('demo-A') & counts.visit_type.eq('15-minute video')].iloc[0]
        self.assertEqual((row.visit_count, row.span_days), (3, 15))
        gaps = self.e.visit_gaps()
        row = gaps.loc[gaps.customer_id.eq('demo-A') & gaps.visit_type.eq('15-minute video')].iloc[0]
        self.assertEqual((row.first_to_second, row.second_to_third), (9, 6))
        self.assertEqual(self.e.visit_summary().completed_visits.sum(), 12)

    def test_report_matching(self):
        d = self.e.report_waits().set_index('report_id')
        self.assertEqual(len(d), 5)
        self.assertEqual(d.loc[103, 'days_to_booking'], 0)
        self.assertEqual(d.loc[101, 'appointment_id'], d.loc[102, 'appointment_id'])
        self.assertTrue(pd.isna(d.loc[104, 'days_to_booking']))
        self.assertTrue(pd.isna(d.loc[105, 'days_to_booking']))
        self.assertEqual(self.e.report_wait_counts().to_numpy().sum(), 5)

    def test_report_tie(self):
        self.a.loc[1, 'created_date'] = self.a.loc[0, 'created_date']
        d = VirtualCareEDA(self.a, self.r).report_waits().set_index('report_id')
        self.assertEqual(d.loc[101, 'first_time_ties'], 2)
        self.assertEqual(d.loc[101, 'appointment_id'], 1)

    def test_nearest_video(self):
        d = self.e.video_to_async().set_index('async_id')
        self.assertEqual((d.loc[5, 'video_id'], d.loc[5, 'gap_days']), (4, 2))
        self.assertEqual(d.loc[2, 'gap_days'], 4)
        self.assertTrue(d.index.is_unique)
        self.assertNotIn(11, d.index)

    def test_transitions_around_ties(self):
        self.assertNotIn('demo-C', self.e.visit_transitions().customer_id.tolist())
        self.assertEqual(self.e.transition_table().to_numpy().sum(), 6)

    def test_satisfaction(self):
        d = self.e.satisfaction_availability()
        self.assertEqual(d.loc['15-minute video', 'Recorded'], 4)
        self.assertEqual(d.loc['Async', 'Not expected'], 3)
        self.assertEqual(d.loc['25-minute video', 'Missing'], 1)
        self.assertEqual(d.loc['Unknown', 'Expectation unknown'], 3)

    def test_missing_dates_and_input_copy(self):
        self.a.loc[0, 'appointment_date'] = pd.NaT
        d = VirtualCareEDA(self.a).visit_counts()
        row = d.loc[d.customer_id.eq('demo-A') & d.visit_type.eq('15-minute video')].iloc[0]
        self.assertEqual((row.visit_count, row.dated_visits, row.span_days), (3, 2, 6))
        self.assertNotIn('visit_type', self.a.columns)

    def test_invalid_ids(self):
        with self.assertRaises(ValueError):
            VirtualCareEDA(self.a, pd.concat([self.r, self.r.iloc[:1]]))
        with self.assertRaises(ValueError):
            VirtualCareEDA(pd.concat([self.a, self.a.iloc[:1]]))

    def test_all_empty_outputs(self):
        e = VirtualCareEDA(self.a.iloc[:0], self.r.iloc[:0])
        for name in ['visit_counts','visit_summary','visit_frequency','visit_gaps','gap_summary',
                     'report_waits','report_summary','report_type_summary','report_wait_counts',
                     'visit_transitions','transition_table','video_to_async','async_summary',
                     'satisfaction_availability','monthly_visits','quality_summary']:
            getattr(e, name)()
        for eda in [self.e, e]:
            p = VirtualCarePlots(eda)
            for name in ['visit_frequency','visit_spans','visit_gaps','report_waits',
                         'transitions','video_to_async','satisfaction','monthly_visits']:
                self.assertTrue(getattr(p, name)().axes)

    def test_cache(self):
        class FakeDB:
            calls = 0
            def query(self, sql):
                self.calls += 1
                return pd.DataFrame()
        db = FakeDB()
        data = VirtualCareData(db)
        _ = data.appointments
        _ = data.appointments
        self.assertEqual(db.calls, 1)
        data.refresh()
        _ = data.appointments
        self.assertEqual(db.calls, 2)

if __name__ == '__main__':
    unittest.main()
