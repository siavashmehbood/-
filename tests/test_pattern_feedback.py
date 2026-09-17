import tempfile
import unittest
from pathlib import Path
from learning.learning_engine import LearningEngine


class PatternFeedbackTests(unittest.TestCase):
    def test_failure_retires_pattern_after_repeated_verified_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = LearningEngine(Path(directory) / 'experiences.json')
            engine.record('بررسی فایل پروژه', 'inspect', 'ok', 1.0, 'command', 'evidence-first', 'verified-task')
            engine.record('بررسی فایل تنظیمات پروژه', 'inspect', 'ok', 1.0, 'command', 'evidence-first', 'verified-task')
            plan = engine.transfer_plan('بررسی فایل جدید پروژه', 'command', 'verified-task')
            self.assertTrue(plan['use_strategy'])
            key = plan['pattern_key']
            first = engine.pattern_feedback(key, 0.0, True, 'verified failure')
            self.assertEqual(first['status'], 'weakened')
            second = engine.pattern_feedback(key, 0.0, True, 'verified failure')
            self.assertEqual(second['status'], 'weakened')
            third = engine.pattern_feedback(key, 0.0, True, 'verified failure')
            self.assertEqual(third['status'], 'retired')
            self.assertFalse(engine.transfer_plan('بررسی فایل جدید پروژه', 'command', 'verified-task').get('use_strategy', False))

    def test_success_reinforces_pattern(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = LearningEngine(Path(directory) / 'experiences.json')
            engine.record('اجرای کار اول پروژه', 'inspect', 'ok', 1.0, 'command', 'primary', 'verified-task')
            engine.record('اجرای کار دوم پروژه', 'inspect', 'ok', 1.0, 'command', 'primary', 'verified-task')
            plan = engine.transfer_plan('اجرای کار سوم پروژه', 'command', 'verified-task')
            before = plan['confidence']
            updated = engine.pattern_feedback(plan['pattern_key'], 1.0, True, 'verified success')
            self.assertEqual(updated['status'], 'active')
            self.assertGreaterEqual(updated['confidence'], before)


if __name__ == '__main__':
    unittest.main()
