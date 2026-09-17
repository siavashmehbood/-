import unittest

from core.reasoning_planning import ReasoningPlanningEngine


class ReasoningPlanningTests(unittest.TestCase):
    def setUp(self):
        self.engine = ReasoningPlanningEngine()

    def test_debug_goal_is_decomposed_and_evidence_weighted(self):
        trace = self.engine.analyze(
            "چرا برنامه خطا می‌دهد؟",
            {"intent": "debug", "goal": "چرا برنامه خطا می‌دهد؟", "constraints": []},
            knowledge=[{"subject": "پایتون", "predicate": "خطا", "object": "وابستگی نصب نشده", "confidence": .95, "source": "test"}],
        )
        self.assertGreaterEqual(len(trace.subgoals), 5)
        self.assertTrue(trace.evidence)
        self.assertTrue(trace.hypotheses)
        self.assertGreater(trace.confidence, .25)
        self.assertFalse(trace.replan_required)

    def test_unknown_goal_does_not_fake_certainty(self):
        trace = self.engine.analyze(
            "دلیل یک پدیده ناشناخته چیست؟",
            {"intent": "question", "goal": "دلیل یک پدیده ناشناخته چیست؟", "constraints": []},
        )
        self.assertEqual(trace.status, "UNKNOWN")
        self.assertGreaterEqual(trace.uncertainty, .65)
        self.assertTrue(trace.assumptions)

    def test_reference_becomes_explicit_decision_input(self):
        trace = self.engine.analyze(
            "ادامه بده",
            {"intent": "general", "goal": "ادامه بده", "constraints": []},
            memory=[("user", "روی پروژه IRAN کار می‌کنیم", "now")],
            reference="پروژه IRAN",
        )
        self.assertIn("مرجع فعال: پروژه IRAN", trace.decisions)
        self.assertTrue(trace.subgoals)

    def test_failed_step_requires_replan(self):
        trace = self.engine.analyze(
            "یک پروژه بساز",
            {"intent": "build", "goal": "یک پروژه بساز", "constraints": []},
            knowledge=[{"subject": "پروژه", "predicate": "وضعیت", "object": "قابل ساخت", "confidence": .9, "source": "test"}],
        )
        self.engine.mark_result(trace, 2, False, "شواهد کافی نبود")
        self.assertTrue(trace.replan_required)
        self.assertEqual(trace.status, "REPLAN_REQUIRED")
        self.assertEqual(trace.steps[1]["status"], "failed")

    def test_all_steps_have_dependency_gates(self):
        trace = self.engine.analyze(
            "برای پروژه برنامه‌ریزی کن",
            {"intent": "planning", "goal": "برای پروژه برنامه‌ریزی کن", "constraints": []},
        )
        self.assertEqual(trace.steps[0]["depends_on"], [])
        for i, step in enumerate(trace.steps[1:], 2):
            self.assertEqual(step["depends_on"], [i-1])
            self.assertEqual(step["gate"], "observable_result")


if __name__ == "__main__":
    unittest.main()
