import unittest
import pandas as pd
from adyn_dash.modules.biomarkers import Biomarkers

class BiomarkerCoverageChecks(unittest.TestCase):
    def test_sample_counts_are_deduplicated_and_unknown_is_retained(self):
        m=object.__new__(Biomarkers)
        m.data=lambda name:pd.DataFrame({'sample_id':[1,1,2,3,4],
            'kind':['KIT-SLV','KIT-SLV','KIT-SLV','KIT-SLV','KIT-BLD'],
            'status':['valid','valid',None,'failed','valid']})
        d=m.dna_sample_quality().set_index('status')
        self.assertEqual(d['samples'].sum(),3)
        self.assertEqual(d.loc['Unknown','samples'],1)
        self.assertAlmostEqual(d['percent'].sum(),100)

    def test_conflicting_sample_status_stops_instead_of_double_counting(self):
        m=object.__new__(Biomarkers)
        m.data=lambda name:pd.DataFrame({'sample_id':[1,1], 'kind':['KIT-SLV']*2,'status':['valid','failed']})
        with self.assertRaises(ValueError):
            m.dna_sample_quality()

    def test_reference_groups_and_missing_bounds(self):
        m=object.__new__(Biomarkers)
        m.hormones=pd.DataFrame({'hormone':['E2']*4,'customer_id':[1,1,2,3],
            'value':[10.,20.,100.,40.], 'ref_low':[0.,0.,0.,None], 'ref_high':[15.,15.,200.,None]})
        d=m.hormone_reference_summary()
        self.assertEqual(len(d),3)
        g=d[d.ref_high.eq(15)].iloc[0]
        self.assertEqual(g['median'],15)
        self.assertEqual(g['patients'],1)
        self.assertEqual(g['percent_out_of_range'],50)
        self.assertTrue(d[d.ref_high.isna()]['percent_out_of_range'].isna().all())
        self.assertTrue(next(s for s in Biomarkers.charts() if s.name=='hormone_reference_summary').internal)

if __name__=='__main__':
    unittest.main()
