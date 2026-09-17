import tempfile
import unittest
from pathlib import Path

from learning.learning_engine import LearningEngine


class LearningTransferPatternTests(unittest.TestCase):
    def test_repeated_successes_create_reusable_pattern(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = LearningEngine(Path(directory) / "experiences.json")
            engine.record("بررسی فایل پروژه", "inspect", "ok", 1.0, "inspect", "evidence-first", "task")
            engine.record("بررسی فایل تنظیمات پروژه", "inspect", "ok", 1.0, "inspect", "evidence-first", "task")
            plan = engine.transfer_plan("بررسی فایل جدید پروژه", "inspect", "task")
            self.assertTrue(plan["available"])
            self.assertEqual(plan["strategy"], "evidence-first")
            self.assertTrue(plan["use_strategy"])
            self.assertGreaterEqual(plan["patterns"][0]["distinct_goals"], 2)

    def test_mixed_pattern_is_not_promoted_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = LearningEngine(Path(directory) / "experiences.json")
            engine.record("بررسی گزارش پروژه", "inspect", "ok", 1.0, "inspect", "same", "task")
            engine.record("بررسی گزارش خطا", "inspect", "bad", 0.1, "inspect", "same", "task")
            plan = engine.transfer_plan("بررسی گزارش جدید", "inspect", "task")
            self.assertTrue(plan["available"])
            self.assertFalse(plan["use_strategy"])


if __name__ == "__main__":
    unittest.main()
