"""Unit tests for the Dynamic MSP Floor engine.

Run from the `chagpt` folder:
    python -m unittest msp_distress.test_distress_engine -v
"""
import unittest

from msp_distress.distress_engine import (
    DistressEngineError,
    bid_meets_floor,
    dwr_loan_advance,
    dynamic_msp_floor,
    effective_quality_adjusted_msp,
    evaluate_floor,
    is_distress_condition,
    quality_multiplier,
    total_holding_expense,
)


class QualityMultiplierTests(unittest.TestCase):
    def test_grade_a(self):
        self.assertEqual(quality_multiplier("A"), 1.10)

    def test_grade_b(self):
        self.assertEqual(quality_multiplier("B"), 1.00)

    def test_grade_c(self):
        self.assertEqual(quality_multiplier("C"), 0.85)

    def test_unknown_grade(self):
        with self.assertRaises(DistressEngineError):
            quality_multiplier("Z")


class FloorMathTests(unittest.TestCase):
    def test_zero_storage_days_grade_b(self):
        f = dynamic_msp_floor(20.0, "B", storage_daily_per_kg=0.35, holding_days=0, logistics_per_kg=0)
        self.assertEqual(f, 20.0)

    def test_zero_storage_days_grade_a(self):
        f = dynamic_msp_floor(20.0, "A", holding_days=0, logistics_per_kg=0)
        self.assertAlmostEqual(f, 22.0, places=4)

    def test_grade_c_multiplier(self):
        self.assertAlmostEqual(effective_quality_adjusted_msp(20.0, "C"), 17.0, places=4)

    def test_nonzero_transport(self):
        f = dynamic_msp_floor(
            p_msp=20.0,
            quality_grade="B",
            storage_daily_per_kg=0.0,
            holding_days=0,
            logistics_per_kg=1.25,
        )
        self.assertAlmostEqual(f, 21.25, places=4)

    def test_storage_plus_logistics_grade_a(self):
        # P_quality = 20 * 1.10 = 22; C_holding = 0.40*7 + 1.50 = 4.3; F = 26.3
        f = dynamic_msp_floor(20.0, "A", 0.40, 7, 1.50)
        self.assertAlmostEqual(f, 26.3, places=4)

    def test_holding_expense(self):
        self.assertAlmostEqual(total_holding_expense(0.5, 10, 2.0), 7.0, places=4)


class DistressTriggerTests(unittest.TestCase):
    def test_forecast_below_msp(self):
        self.assertTrue(is_distress_condition(15, 20))

    def test_offer_below_floor(self):
        self.assertTrue(is_distress_condition(25, 20, p_current_offer=21, f_dynamic=22))

    def test_healthy_market(self):
        self.assertFalse(is_distress_condition(25, 20, p_current_offer=23, f_dynamic=22))


class BidFloorTests(unittest.TestCase):
    def test_reject_below_floor(self):
        self.assertFalse(bid_meets_floor(21.99, 22.00))

    def test_accept_at_floor(self):
        self.assertTrue(bid_meets_floor(22.00, 22.00))

    def test_accept_above_floor(self):
        self.assertTrue(bid_meets_floor(24.50, 22.00))


class LoanTests(unittest.TestCase):
    def test_seventy_percent_ltv(self):
        self.assertEqual(dwr_loan_advance(10000), 7000.0)


class EvaluateBreakdownTests(unittest.TestCase):
    def test_breakdown_keys(self):
        b = evaluate_floor(
            p_msp=20,
            quality_grade="A",
            p_mandi_predicted=18,
            storage_daily_per_kg=0.3,
            holding_days=5,
            logistics_per_kg=1.0,
            p_current_offer=19,
        )
        self.assertTrue(b.is_distress)
        self.assertIn("P_mandi_predicted < P_MSP", b.trigger_reasons)
        self.assertAlmostEqual(b.p_msp_quality, 22.0, places=4)
        self.assertAlmostEqual(b.c_holding, 2.5, places=4)
        self.assertAlmostEqual(b.f_dynamic, 24.5, places=4)


if __name__ == "__main__":
    unittest.main()
