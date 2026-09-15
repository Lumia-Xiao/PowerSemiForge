from __future__ import annotations

from pathlib import Path
import unittest

from switching_loss_engine.api import device_library_root, project_root
from switching_loss_engine.validation import ValidationDataset, evaluate_dataset, parasitic_uncertainty


class Phase5ValidationTests(unittest.TestCase):
    def test_holdout_is_separate_and_within_v1_threshold(self):
        root = project_root()
        dataset = ValidationDataset.load(device_library_root(root) / "wolfspeed/C2M0025120D/validation/phase5_xml_holdout_v1.yaml")
        report = evaluate_dataset(dataset, root)
        self.assertEqual(report["holdout_count"], 2)
        self.assertEqual(report["calibration_count"], 5)
        self.assertLess(report["eon"]["mape_pct"], 10)
        self.assertLess(report["eoff"]["mape_pct"], 12)

    def test_uncertainty_is_deterministic(self):
        a = parasitic_uncertainty(samples=2, seed=7)
        b = parasitic_uncertainty(samples=2, seed=7)
        self.assertEqual(a, b)
        self.assertLess(a["eon_J"]["p05"], a["eon_J"]["p95"])


if __name__ == "__main__":
    unittest.main()
