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

    def test_conflicting_high_confidence_facts_cannot_fake_verified_certainty(self):
        trace = self.engine.analyze(
            "service state?",
            {"intent": "question", "goal": "service state?", "constraints": []},
            knowledge=[
                {"subject": "service", "predicate": "state", "object": "online", "confidence": .98, "source": "a"},
                {"subject": "service", "predicate": "state", "object": "offline", "confidence": .97, "source": "b"},
            ],
        )
        self.assertEqual(trace.status, "CONFLICTING")
        self.assertLess(trace.confidence, .65)
        self.assertGreaterEqual(trace.uncertainty, .51)
        self.assertTrue(trace.contradictions)

    def test_evidence_strength_maps_to_calibrated_states(self):
        probable = self.engine.analyze(
            "direct explanation?",
            {"intent": "question", "goal": "direct explanation", "constraints": []},
            knowledge=[{"subject": "direct", "predicate": "explanation", "object": "context",
                        "confidence": .55, "source": "test"}],
        )
        self.assertEqual(probable.status, "UNCERTAIN")
        self.assertGreater(probable.confidence, .0)
        self.assertLess(probable.confidence, .45)

        uncertain = self.engine.analyze(
            "direct explanation?",
            {"intent": "question", "goal": "direct explanation", "constraints": []},
            memory=[("event", "unrelated weak context", "now")],
        )
        self.assertIn(uncertain.status, {"UNCERTAIN", "PROBABLE"})
        self.assertGreater(uncertain.uncertainty, .35)

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


    def test_step_cannot_complete_before_dependency(self):
        trace = self.engine.analyze(
            "یک پروژه بساز",
            {"intent": "build", "goal": "یک پروژه بساز", "constraints": []},
        )
        self.engine.mark_result(trace, 3, True, "premature")
        self.assertEqual(trace.steps[2]["status"], "blocked")
        self.assertEqual(trace.steps[2]["blocked_by"], [2])
        self.assertTrue(trace.replan_required)

    def test_capability_matrix_covers_grounded_reasoning_and_uncertainty(self):
        grounded = self.engine.analyze(
            "چرا سرویس خطا می‌دهد؟",
            {"intent": "debug", "goal": "رفع خطای سرویس", "constraints": []},
            knowledge=[{"subject": "سرویس", "predicate": "خطا",
                        "object": "پیکربندی ناسازگار", "confidence": .95,
                        "source": "benchmark"}],
        )
        self.assertEqual(grounded.status, "VERIFIED_CANDIDATE")
        self.assertGreaterEqual(len(grounded.subgoals), 5)
        self.assertEqual(grounded.steps[1]["depends_on"], [1])

        unknown = self.engine.analyze(
            "علت پدیده ناشناخته چیست؟",
            {"intent": "question", "goal": "علت پدیده ناشناخته چیست؟", "constraints": []},
        )
        self.assertEqual(unknown.status, "UNKNOWN")
        self.assertGreaterEqual(unknown.uncertainty, .65)

    def test_plan_completes_only_after_ordered_verified_steps(self):
        trace = self.engine.analyze(
            "یک پروژه بساز",
            {"intent": "build", "goal": "یک پروژه بساز", "constraints": []},
        )
        for step in trace.steps:
            self.engine.mark_result(trace, step["id"], True, "verified")
        self.assertEqual(trace.status, "COMPLETED")
        self.assertFalse(trace.replan_required)


if __name__ == "__main__":
    unittest.main()
