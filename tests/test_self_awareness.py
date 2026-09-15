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

    def test_self_assesses_domains(self):
        engine = SelfAwarenessEngine()
        for _ in range(5):
            engine.observe("goal", "project_files", .9, True)
        for _ in range(5):
            engine.observe("goal", "project_summary", .2, False)
        view = engine.introspect()
        self.assertIn("perception", view["self_model"]["capability_domains"])
        self.assertIn("understanding", view["self_model"]["capability_domains"])
        self.assertIn("understanding", " ".join(view["self_model"]["known_limits"]))
        self.assertIn("weakest_domains", view)

    def test_control_next_action_persists_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "self_model.json"
            engine = SelfAwarenessEngine(path)
            for _ in range(5):
                engine.observe("goal", "project_files", .9, True)
            for _ in range(5):
                engine.observe("goal", "project_summary", .2, False)
            control = engine.control_next_action(["project_summary", "project_files"])
            self.assertEqual(control["preferred_action"], "project_files")
            restarted = SelfAwarenessEngine(path)
            self.assertEqual(restarted.state.preferred_action, "project_files")

    def test_calibration_changes_control_reason(self):
        engine = SelfAwarenessEngine()
        for _ in range(5):
            engine.observe("goal", "project_files", .1, False, expected=.9)
        control = engine.control_next_action(["project_files", "project_summary"])
        self.assertEqual(control["reason"], "best capability under low calibration confidence")


if __name__ == "__main__":
    unittest.main()
