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

    def test_cross_goal_transfer(self):
        engine = SelfAwarenessEngine()
        for _ in range(6):
            engine.observe("inspect project changes", "project_files", .9, True)
        for _ in range(2):
            engine.observe("inspect project changes", "project_summary", .2, False)
        result = engine.transfer_control(
            "understand what changed in the workspace",
            ["project_summary", "project_files"],
        )
        self.assertEqual(result["preferred_action"], "project_files")
        self.assertGreater(result["transfer_confidence"], .6)

    def test_transfer_penalizes_miscalibration(self):
        engine = SelfAwarenessEngine()
        for _ in range(5):
            engine.observe("goal", "project_files", .9, True, expected=.2)
        score = engine.transfer_score("new goal", "project_files")
        self.assertLess(score, engine.state.capability["project_files"])

    def test_comprehensive_evaluation_acts_when_capable(self):
        engine = SelfAwarenessEngine()
        for _ in range(6):
            engine.observe("goal", "project_files", .95, True)
        result = engine.evaluate_action("goal", "project_files", .9, .9, .05, .9, 1.0, True)
        self.assertEqual(result["decision"], "act")
        self.assertLess(result["risk"], .52)
        self.assertIn("calibration_confidence", result)

    def test_comprehensive_evaluation_gathers_evidence_when_weak(self):
        engine = SelfAwarenessEngine()
        for _ in range(2):
            engine.observe("goal", "project_files", .1, False, expected=.8)
        result = engine.evaluate_action("new goal", "project_files", .8, .2, .8, .8, 1.0, True)
        self.assertEqual(result["decision"], "gather_evidence")
        self.assertTrue(result["reasons"])
        self.assertGreaterEqual(result["risk"], .52)

    def test_comprehensive_evaluation_avoids_unsafe_action(self):
        engine = SelfAwarenessEngine()
        result = engine.evaluate_action("goal", "unknown", .9, .9, .1, .9, .2, True)
        self.assertEqual(result["decision"], "avoid")
        self.assertIn("elevated safety concern", result["reasons"])

    def test_comprehensive_evaluation_requires_verification(self):
        engine = SelfAwarenessEngine()
        for _ in range(6):
            engine.observe("goal", "project_files", .9, True)
        result = engine.evaluate_action("goal", "project_files", .9, .9, .0, .9, 1.0, False)
        self.assertEqual(result["decision"], "gather_evidence")
        self.assertIn("verification unavailable", result["reasons"])

    def test_evaluation_snapshot_compares_candidates(self):
        engine = SelfAwarenessEngine()
        for _ in range(5):
            engine.observe("goal", "project_files", .9, True)
        snapshot = engine.evaluation_snapshot(["project_summary", "project_files"], "goal")
        self.assertEqual(len(snapshot["evaluations"]), 2)
        self.assertIn(snapshot["recommended"]["decision"], {"act", "gather_evidence", "avoid"})

    def test_plan_evaluation_finds_weakest_step(self):
        engine = SelfAwarenessEngine()
        for _ in range(6):
            engine.observe("goal", "project_files", .9, True)
        result = engine.evaluate_plan("goal", ["project_files", "memory_search"], .8, .8)
        self.assertEqual(len(result["steps"]), 2)
        self.assertIn(result["decision"], {"act", "gather_evidence", "avoid"})
        self.assertIsNotNone(result["weakest_step"])

    def test_outcome_evaluation_detects_overconfidence(self):
        engine = SelfAwarenessEngine()
        evaluation = engine.evaluate_action("goal", "project_files", .9, .9, .0, .9, 1.0, True)
        outcome = engine.evaluate_outcome(evaluation, .2, False)
        self.assertEqual(outcome["calibration_direction"], "overconfident")
        self.assertGreater(outcome["error"], .5)

    def test_goal_evaluation_distinguishes_clarification(self):
        engine = SelfAwarenessEngine()
        result = engine.evaluate_goal("unknown goal", evidence_confidence=.2, novelty=.9, feasibility=.7)
        self.assertEqual(result["decision"], "clarify")
        self.assertGreaterEqual(result["ambiguity"], .8)

    def test_goal_evaluation_rejects_infeasible_goal(self):
        engine = SelfAwarenessEngine()
        result = engine.evaluate_goal("goal", evidence_confidence=.9, novelty=.2, feasibility=.1, safety=1.)
        self.assertEqual(result["decision"], "avoid")

    def test_prediction_evaluation_requires_verification(self):
        engine = SelfAwarenessEngine()
        result = engine.evaluate_prediction(.8, .4, .3, .7)
        self.assertEqual(result["decision"], "verify")
        self.assertGreater(result["risk"], .35)

    def test_prediction_evaluation_rejects_low_reliability(self):
        engine = SelfAwarenessEngine()
        result = engine.evaluate_prediction(.2, .1, .1, .9)
        self.assertEqual(result["decision"], "reject")

    def test_calibration_update_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"self_model.json"
            engine=SelfAwarenessEngine(path)
            result=engine.calibration_update(.9,.2,False)
            self.assertGreater(result["calibration_error"],0)
            restarted=SelfAwarenessEngine(path)
            self.assertEqual(restarted.state.calibration_error,result["calibration_error"])



if __name__ == "__main__":
    unittest.main()
