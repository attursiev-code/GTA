import unittest

from gtm_selector.models import Well, GtmType, Candidate
from gtm_selector.params import EconomicParams
from gtm_selector.economics import evaluate_economics


class EconomicsTestCase(unittest.TestCase):
    def setUp(self):
        self.well = Well(id="1", name="Test")
        self.econ = EconomicParams(
            oil_price=30000,
            opex_per_ton=10000,
            effect_duration_months=12,
            monthly_decline_pct=0.0,
        )

    def test_zero_delta_gives_no_effect(self):
        candidate = Candidate(GtmType.OPZ, True, [], delta_qo=0.0)
        rec = evaluate_economics(self.well, candidate, self.econ)
        self.assertEqual(rec.incremental_production, 0.0)
        self.assertEqual(rec.revenue, 0.0)
        self.assertLess(rec.economic_effect, 0)  # cost > 0, revenue 0

    def test_positive_delta_gives_positive_revenue(self):
        candidate = Candidate(GtmType.OPZ, True, [], delta_qo=5.0)
        rec = evaluate_economics(self.well, candidate, self.econ)
        expected_production = 5.0 * 30.4 * 12
        self.assertAlmostEqual(rec.incremental_production, expected_production, places=3)
        expected_revenue = expected_production * (30000 - 10000)
        self.assertAlmostEqual(rec.revenue, expected_revenue, places=3)
        self.assertAlmostEqual(rec.economic_effect, expected_revenue - rec.cost, places=3)

    def test_decline_reduces_production_vs_flat(self):
        flat_econ = EconomicParams(
            oil_price=30000, opex_per_ton=10000,
            effect_duration_months=12, monthly_decline_pct=0.0,
        )
        declining_econ = EconomicParams(
            oil_price=30000, opex_per_ton=10000,
            effect_duration_months=12, monthly_decline_pct=5.0,
        )
        candidate = Candidate(GtmType.GRP, True, [], delta_qo=10.0)
        flat_rec = evaluate_economics(self.well, candidate, flat_econ)
        decl_rec = evaluate_economics(self.well, candidate, declining_econ)
        self.assertLess(decl_rec.incremental_production, flat_rec.incremental_production)

    def test_payback_computed_when_cost_recovered(self):
        candidate = Candidate(GtmType.OPZ, True, [], delta_qo=100.0)  # huge uplift
        rec = evaluate_economics(self.well, candidate, self.econ)
        self.assertIsNotNone(rec.payback_months)
        self.assertGreaterEqual(rec.payback_months, 1)

    def test_payback_none_when_never_recovered(self):
        candidate = Candidate(GtmType.GRP, True, [], delta_qo=0.01)
        rec = evaluate_economics(self.well, candidate, self.econ)
        self.assertIsNone(rec.payback_months)

    def test_roi_none_when_cost_zero(self):
        econ = EconomicParams(oil_price=30000, opex_per_ton=10000)
        econ.cost_by_type = {k: 0.0 for k in econ.cost_by_type}
        candidate = Candidate(GtmType.OPZ, True, [], delta_qo=5.0)
        rec = evaluate_economics(self.well, candidate, econ)
        self.assertIsNone(rec.roi)


if __name__ == "__main__":
    unittest.main()
