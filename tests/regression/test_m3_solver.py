from __future__ import annotations

import unittest

from switching_loss_engine import CalculationRequest, OperatingPointInput, calculate


class M3SolverRegressionTests(unittest.TestCase):
    def test_stages_are_present_and_time_is_continuous(self):
        result = calculate(CalculationRequest(
            "C2M0025120D", "M3", OperatingPointInput(800, 50, 25, 2.5, 2.5),
            calibration_id="m3_datasheet_table_v1", return_waveforms=True, convergence_check=False,
        ))
        self.assertTrue(result.solver.converged)
        for event, expected in (("turn_on", {"gate_delay", "current_rise", "reverse_recovery", "voltage_fall"}),
                                ("turn_off", {"gate_discharge", "voltage_rise", "current_fall"})):
            records = result.waveforms[event]
            times = [row["t_s"] for row in records]
            self.assertTrue(all(b > a for a, b in zip(times, times[1:])))
            self.assertTrue(expected.issubset({row["stage"] for row in records}))

    def test_half_step_convergence(self):
        result = calculate(CalculationRequest(
            "C2M0025120D", "M3", OperatingPointInput(800, 50, 25, 2.5, 2.5),
            calibration_id="m3_datasheet_table_v1", convergence_check=True,
        ))
        self.assertTrue(result.solver.converged)
        self.assertLess(result.solver.eon_relative_change, 0.08)
        self.assertLess(result.solver.eoff_relative_change, 0.08)

    def test_temperature_and_low_current_trends(self):
        low = calculate(CalculationRequest("C2M0025120D", "M3", OperatingPointInput(800, 12.56, 25, 5, 5), convergence_check=False))
        high = calculate(CalculationRequest("C2M0025120D", "M3", OperatingPointInput(800, 48.07, 25, 5, 5), convergence_check=False))
        hot = calculate(CalculationRequest("C2M0025120D", "M3", OperatingPointInput(800, 48.07, 125, 5, 5), convergence_check=False))
        self.assertLess(low.energy.eon_J, high.energy.eon_J)
        self.assertLess(low.energy.eoff_J, high.energy.eoff_J)
        self.assertGreater(hot.energy.eon_J, high.energy.eon_J)
        self.assertGreater(hot.energy.eoff_J, high.energy.eoff_J)


if __name__ == "__main__":
    unittest.main()

