import unittest

from gtm_selector.engine import select_gtm, best_recommendation_per_well
from gtm_selector.params import Settings
from gtm_selector.sample_data import make_sample_wells


class EngineTestCase(unittest.TestCase):
    def test_select_gtm_returns_sorted_profitable_recommendations(self):
        wells = make_sample_wells()
        settings = Settings()
        recs = select_gtm(wells, settings, only_profitable=True)
        self.assertGreater(len(recs), 0)
        for r in recs:
            self.assertGreater(r.economic_effect, 0)
        effects = [r.economic_effect for r in recs]
        self.assertEqual(effects, sorted(effects, reverse=True))

    def test_select_gtm_all_includes_nonprofitable(self):
        wells = make_sample_wells()
        settings = Settings()
        recs_profit = select_gtm(wells, settings, only_profitable=True)
        recs_all = select_gtm(wells, settings, only_profitable=False)
        self.assertGreaterEqual(len(recs_all), len(recs_profit))

    def test_best_recommendation_per_well_unique_wells(self):
        wells = make_sample_wells()
        settings = Settings()
        recs = select_gtm(wells, settings, only_profitable=False)
        best = best_recommendation_per_well(recs)
        well_ids = [r.well_id for r in best]
        self.assertEqual(len(well_ids), len(set(well_ids)))
        for well_id in set(r.well_id for r in recs):
            candidates = [r for r in recs if r.well_id == well_id]
            top = max(c.economic_effect for c in candidates)
            chosen = next(r for r in best if r.well_id == well_id)
            self.assertEqual(chosen.economic_effect, top)


if __name__ == "__main__":
    unittest.main()
