from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from powersemiforge.batch import expand_matrix, load_matrix, run_batch
from powersemiforge.reporting import build_report


class PipelineBatchTests(unittest.TestCase):
    def test_matrix_expansion_is_deterministic(self):
        config = load_matrix(Path(__file__).parents[2] / "examples" / "batch_matrix.yaml")
        first = expand_matrix(config)
        second = expand_matrix(config)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)

    def test_batch_and_report_end_to_end(self):
        matrix = Path(__file__).parents[2] / "examples" / "batch_matrix.yaml"
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            manifest = run_batch(matrix, run_dir)
            self.assertEqual(manifest["jobs"], 12)
            self.assertEqual(manifest["failed"], 0)
            report = build_report(run_dir / "results.csv", Path(temp) / "report")
            self.assertEqual(report["rows"], 12)
            self.assertEqual(report["groups"], 1)
            self.assertTrue(Path(report["figures"][0]).exists())
            saved = json.loads((run_dir / "run-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["run_id"], manifest["run_id"])


if __name__ == "__main__":
    unittest.main()

