import tempfile
import unittest
from pathlib import Path

from self.evaluator import Evaluator


class EvaluatorQualityTests(unittest.TestCase):
    def test_direct_answer_scores_higher_than_internal_dump(self):
        evaluator = Evaluator(Path(tempfile.mkdtemp()))
        direct = evaluator.evaluate_answer('پایتخت ایران کجاست؟', 'پایتخت ایران تهران است.', ['تهران'])
        internal = evaluator.evaluate_answer('پایتخت ایران کجاست؟', 'intent = question hypotheses = []')
        self.assertGreater(direct['directness'], internal['directness'])
        self.assertGreater(direct['overall'], internal['overall'])

    def test_unknown_is_calibrated(self):
        evaluator = Evaluator(Path(tempfile.mkdtemp()))
        result = evaluator.evaluate_answer('سؤال ناشناخته', 'UNKNOWN: داده کافی ندارم.', unknown=True)
        self.assertGreaterEqual(result['uncertainty_calibration'], .9)


if __name__ == '__main__':
    unittest.main()
