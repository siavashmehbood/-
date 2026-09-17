import unittest

from core.adaptive_execution import AdaptiveExecutionPolicy


class AdaptiveExecutionPolicyTests(unittest.TestCase):
    def test_requires_evidence(self):
        decision = AdaptiveExecutionPolicy().decide('correct', 'correct', [], 0)
        self.assertFalse(decision.success)
        self.assertTrue(decision.should_replan)

    def test_rejects_mismatched_observation(self):
        decision = AdaptiveExecutionPolicy().decide('correct', 'wrong', ['recheck'], 0)
        self.assertFalse(decision.success)
        self.assertTrue(decision.should_replan)

    def test_accepts_verified_expected_effect(self):
        decision = AdaptiveExecutionPolicy().decide('correct', 'result is correct', ['recheck'], 1)
        self.assertTrue(decision.success)
        self.assertFalse(decision.should_replan)

    def test_replan_is_bounded(self):
        decision = AdaptiveExecutionPolicy(max_replans=1).decide('correct', 'wrong', ['recheck'], 2)
        self.assertFalse(decision.success)
        self.assertFalse(decision.should_replan)


if __name__ == '__main__':
    unittest.main()
