import tempfile
import unittest
from pathlib import Path
from learning.learning_engine import LearningEngine

class LearningTransferTests(unittest.TestCase):
    def test_persistent_approved_learning_improves_future_task(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'experiences.json'
            before = LearningEngine(path)
            baseline = {'score': 0.35}
            before.record('ساخت ابزار آفلاین کوچک', 'evidence-first', 'ok', .95, 'build', 'evidence-first', 'tools')
            before.record('ساخت ابزار آفلاین امن', 'evidence-first', 'ok', .90, 'build', 'evidence-first', 'tools')
            after_restart = LearningEngine(path)

            def apply(payload):
                return bool(payload['rule']['samples'] >= 2)

            def verify(task, applied):
                return {'score': .90 if applied else .35, 'verified': applied,
                        'decision_before': 'collect evidence before committing',
                        'decision_after': 'reuse successful strategy, then verify',
                        'procedure_retrieved': True}

            transfer = after_restart.transfer_real(
                'ساخت ابزار آفلاین کوچک', 'ساخت ابزار آفلاین جدید',
                lambda task: baseline['score'], apply, verify)
            self.assertTrue(transfer['transfer_success'])
            self.assertGreater(transfer['improvement'], 0)
            self.assertEqual(transfer['decision_after'], 'reuse successful strategy, then verify')

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
