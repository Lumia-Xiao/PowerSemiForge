from __future__ import annotations

import unittest

from switching_loss_engine import CalculationRequest, OperatingPointInput, ParasiticsInput, available_devices, calculate
from switching_loss_engine.exceptions import InputValidationError


class DeviceAndApiTests(unittest.TestCase):
    def test_device_is_registered(self):
        self.assertEqual(available_devices(), ["C2M0025120D"])

    def test_invalid_input_is_rejected(self):
        with self.assertRaises(InputValidationError):
            calculate(CalculationRequest("C2M0025120D", "M3", OperatingPointInput(0, 50)))

    def test_reference_anchors_for_m0_m1_m2(self):
        op = OperatingPointInput(800, 50, 25, 2.5, 2.5)
        for model in ("M0", "M1", "M2"):
            with self.subTest(model=model):
                result = calculate(CalculationRequest("C2M0025120D", model, op, convergence_check=False))
                self.assertAlmostEqual(result.energy.eon_J, 2.18e-3, places=10)
                self.assertAlmostEqual(result.energy.eoff_J, 0.68e-3, places=10)
                self.assertTrue(result.solver.converged)

    def test_m3_xml_reference_anchor(self):
        op = OperatingPointInput(800, 48.07, 25, 5, 5)
        result = calculate(CalculationRequest("C2M0025120D", "M3", op, convergence_check=False))
        self.assertAlmostEqual(result.energy.eon_J, 1.567e-3, places=10)
        self.assertAlmostEqual(result.energy.eoff_J, 0.21448e-3, places=10)

    def test_fixed_profile_is_not_refit_for_changed_parasitics(self):
        op = OperatingPointInput(800, 48.07, 25, 5, 5)
        nominal = calculate(CalculationRequest("C2M0025120D", "M3", op, convergence_check=False))
        changed = calculate(CalculationRequest(
            "C2M0025120D", "M3", op,
            ParasiticsInput(lg_H=9e-9, ls_H=8e-9, lloop_H=35e-9), convergence_check=False,
        ))
        self.assertEqual(nominal.calibration_id, changed.calibration_id)
        self.assertNotAlmostEqual(nominal.energy.esw_J, changed.energy.esw_J, places=8)
        self.assertTrue(any("not refit" in warning for warning in changed.warnings))


if __name__ == "__main__":
    unittest.main()

