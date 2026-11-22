import unittest
import pandas as pd
from adyn_dash.modules.virtual_care import VirtualCare
from adyn_dash.lib.virtual_care.demo import synthetic_data
from adyn_dash.lib.virtual_care.analysis import VirtualCareEDA

class Updates(unittest.TestCase):
    def setUp(self):
        self.module = object.__new__(VirtualCare)
        a, r = synthetic_data()
        self.module.eda = VirtualCareEDA(a, r)
        self.cohort = pd.DataFrame({
            'customer_id': ['demo-A', 'no-visits'],
            'por_approved': [True, True],
            'first_viewed_date': ['2024-01-01', None]})
        self.module.data = lambda name: self.cohort.copy()

    def test_zero_visits_and_denominators(self):
        out = self.module.approved_visit_frequency()
        for _, group in out.groupby('visit_type'):
            self.assertEqual(group.customers.sum(), 2)
            self.assertEqual(group.percent.sum(), 100)
        all_types = out.loc[out.visit_type.eq('All visit types')]
        self.assertEqual(all_types.loc[all_types.visit_group.eq('0'), 'customers'].item(), 1)

    def test_empty_denominator_is_unknown_not_zero_percent(self):
        self.cohort['por_approved'] = False
        self.assertTrue(self.module.approved_visit_frequency().percent.isna().all())

    def test_completion_is_subset_of_booking(self):
        out = self.module.viewer_conversion().set_index('outcome')
        self.assertEqual(out.denominator.unique().tolist(), [1])
        self.assertLessEqual(out.loc['Completed', 'customers'], out.loc['Booked', 'customers'])
        self.assertEqual(out.loc['Booked without observed completion', 'customers'],
                         out.loc['Booked', 'customers'] - out.loc['Completed', 'customers'])

    def test_span_combines_types(self):
        result = self.module.overall_visit_span().iloc[0]
        a = self.module.eda.completed
        dated = a.groupby('customer_id').appointment_date.count()
        self.assertEqual(result.customers_with_usable_span, int(dated.ge(2).sum()))
