import tempfile
import unittest
from pathlib import Path
from learning.learning_engine import LearningEngine

class LearningTransferTests(unittest.TestCase):
    def test_successful_rule_transfers_from_a_to_b(self):
        with tempfile.TemporaryDirectory() as d:
            learner = LearningEngine(Path(d) / 'experiences.json')
            learner.record('ساخت ابزار امن محلی', 'evidence-first', 'ok', .95, 'build', 'evidence-first', 'tools')
            learner.record('ساخت ابزار امن کوچک', 'evidence-first', 'ok', .90, 'build', 'evidence-first', 'tools')
            transfer = learner.transfer('ساخت ابزار امن محلی', 'ساخت ابزار امن جدید')
            self.assertTrue(transfer['transferred'])
            self.assertTrue(transfer['decision_changed'])
            self.assertEqual(transfer['decision'], 'reuse successful strategy, then verify')
            self.assertGreaterEqual(transfer['rule']['confidence'], .5)

if __name__ == '__main__':
    unittest.main()
