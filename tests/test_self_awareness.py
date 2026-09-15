import tempfile
import unittest
from pathlib import Path

from core.self_awareness import SelfAwarenessEngine


class SelfAwarenessTests(unittest.TestCase):
    def test_success_changes_future_priority(self):
        engine = SelfAwarenessEngine()
        engine.observe("restore system", "project_files", .9, True)
        engine.observe("restore system", "project_summary", .2, False)
        ranked = engine.reassess(["project_summary", "project_files"])
        self.assertEqual(ranked[0], "project_files")

    def test_failure_creates_uncertainty(self):
        engine = SelfAwarenessEngine()
        engine.observe("goal", "bad_action", .1, False, failure_reason="verification failed")
        view = engine.introspect()
        self.assertIn("verification failed", view["self_model"]["uncertainty"])
        self.assertGreater(view["self_model"]["recent_failures"], 0)

    def test_calibration_error_reduces_confidence(self):
        engine = SelfAwarenessEngine()
        engine.observe("goal", "action", .2, True, expected=.9)
        self.assertLess(engine.state.confidence, .5)

    def test_self_model_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "self_model.json"
            first = SelfAwarenessEngine(path)
            first.observe("goal", "project_files", .9, True)
            second = SelfAwarenessEngine(path)
            self.assertEqual(second.state.active_goal, "goal")
            self.assertIn("project_files", second.state.capability)
            self.assertGreater(second.state.recent_successes, 0)


if __name__ == "__main__":
    unittest.main()
