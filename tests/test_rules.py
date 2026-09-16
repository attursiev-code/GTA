import unittest

from gtm_selector.models import Well, GtmType
from gtm_selector.params import Thresholds
from gtm_selector.rules import evaluate_well, check_pump


def make_well(**overrides) -> Well:
    base = dict(
        id="1", name="Test", formation="F", status="active",
        qo=10.0, ql=12.0, watercut=10.0,
        p_res=200, p_res_initial=240, p_wf=90,
        skin=1.0, perm=30.0, thickness_total=10.0, thickness_perforated=10.0,
        reserves_remaining=30.0, depletion=30.0,
        pump_capacity=20.0, idle_days=0, last_active_qo=0.0,
        months_since_last_gtm=24,
    )
    base.update(overrides)
    return Well(**base)


class RulesTestCase(unittest.TestCase):
    def setUp(self):
        self.t = Thresholds()

    def test_opz_triggers_on_high_skin(self):
        well = make_well(skin=9.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertIn(GtmType.OPZ, types)
        opz = next(c for c in candidates if c.gtm_type == GtmType.OPZ)
        self.assertGreater(opz.delta_qo, 0)

    def test_opz_does_not_trigger_on_low_skin(self):
        well = make_well(skin=0.5)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertNotIn(GtmType.OPZ, types)

    def test_grp_triggers_on_low_perm_low_watercut(self):
        well = make_well(perm=5.0, watercut=20.0, depletion=30.0, skin=0.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertIn(GtmType.GRP, types)

    def test_grp_blocked_by_high_watercut(self):
        well = make_well(perm=5.0, watercut=80.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertNotIn(GtmType.GRP, types)

    def test_rir_triggers_on_high_watercut(self):
        well = make_well(watercut=90.0, depletion=50.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertIn(GtmType.RIR, types)

    def test_zbs_requires_reserves(self):
        well = make_well(watercut=98.0, reserves_remaining=1.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertNotIn(GtmType.ZBS, types)

        well2 = make_well(watercut=98.0, reserves_remaining=10.0)
        candidates2 = evaluate_well(well2, self.t)
        types2 = {c.gtm_type for c in candidates2}
        self.assertIn(GtmType.ZBS, types2)

    def test_pump_up_when_overloaded(self):
        well = make_well(ql=19.0, pump_capacity=20.0)  # util=0.95
        c = check_pump(well, self.t)
        self.assertIsNotNone(c)
        self.assertTrue(c.matched)
        self.assertEqual(c.gtm_type, GtmType.PUMP_UP)

    def test_pump_down_when_underloaded(self):
        well = make_well(ql=5.0, pump_capacity=20.0)  # util=0.25
        c = check_pump(well, self.t)
        self.assertIsNotNone(c)
        self.assertTrue(c.matched)
        self.assertEqual(c.gtm_type, GtmType.PUMP_DOWN)

    def test_pump_none_without_capacity(self):
        well = make_well(pump_capacity=0.0)
        c = check_pump(well, self.t)
        self.assertIsNone(c)

    def test_perforation_triggers_on_unopened_thickness(self):
        well = make_well(thickness_total=20.0, thickness_perforated=10.0, reserves_remaining=10.0)
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertIn(GtmType.PERFORATION, types)

    def test_reactivation_for_idle_well(self):
        well = make_well(
            status="idle", qo=0, ql=0, watercut=0,
            idle_days=200, last_active_qo=8.0, reserves_remaining=20.0,
        )
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertIn(GtmType.REACTIVATION, types)
        rec = next(c for c in candidates if c.gtm_type == GtmType.REACTIVATION)
        self.assertLess(rec.delta_qo, well.last_active_qo)  # decline applied
        self.assertGreater(rec.delta_qo, 0)

    def test_reactivation_skipped_when_too_long_idle(self):
        well = make_well(
            status="idle", qo=0, ql=0, watercut=0,
            idle_days=5000, last_active_qo=8.0, reserves_remaining=20.0,
        )
        candidates = evaluate_well(well, self.t)
        types = {c.gtm_type for c in candidates}
        self.assertNotIn(GtmType.REACTIVATION, types)

    def test_no_candidates_if_recent_gtm(self):
        well = make_well(skin=9.0, months_since_last_gtm=1)
        candidates = evaluate_well(well, self.t)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
