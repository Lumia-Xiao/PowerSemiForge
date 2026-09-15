from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from switching_loss_engine import CalculationRequest, OperatingPointInput, calculate
from switching_loss_engine.exporting import export_json, export_summary_csv, export_waveform_csvs
from switching_loss_engine.plotting import plot_waveforms


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = calculate(CalculationRequest(
            "C2M0025120D", "M3", OperatingPointInput(800, 36.71, 25, 5, 5),
            return_waveforms=True, convergence_check=False,
        ))

    def test_json_csv_waveforms_and_plot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            json_path = export_json(self.result, root / "summary.json")
            csv_path = export_summary_csv(self.result, root / "summary.csv")
            waveform_paths = export_waveform_csvs(self.result, root / "waveforms")
            plot_path = plot_waveforms(self.result, root / "waveforms.png")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["device_id"], "C2M0025120D")
            self.assertGreater(csv_path.stat().st_size, 100)
            self.assertEqual(set(waveform_paths), {"turn_on", "turn_off"})
            self.assertGreater(plot_path.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
