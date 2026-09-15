from __future__ import annotations

from pathlib import Path
import unittest


class PlanWorkflowTests(unittest.TestCase):
    def test_at_most_one_active_markdown_plan(self):
        root = Path(__file__).resolve().parents[2]
        active = root / "Plan" / "Active"
        plans = list(active.glob("*.md")) if active.exists() else []
        self.assertLessEqual(
            len(plans),
            1,
            f"Plan/Active must contain at most one Markdown plan, found: {[path.name for path in plans]}",
        )


if __name__ == "__main__":
    unittest.main()
