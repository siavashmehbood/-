import unittest
from evaluation.language.experiment import ExperimentSpec,validate_comparison
from evaluation.language.promotion import select_foundation


def spec(candidate,round_,temp=.2):
    return ExperimentSpec(candidate,candidate+"/model","abc123",round_,"q4",32768,temp,512)


class ExperimentPromotionTests(unittest.TestCase):
    def test_both_rounds_required(self):
        with self.assertRaises(ValueError): validate_comparison([spec("a","quality_baseline")])

    def test_quality_settings_must_match(self):
        with self.assertRaises(ValueError):
            validate_comparison([spec("a","quality_baseline"),spec("a","deployment"),
                                 spec("b","quality_baseline",.4),spec("b","deployment")])

    def test_no_evidence_means_no_winner(self):
        result=select_foundation([{"candidate_id":"qwen"}])
        self.assertIsNone(result["selected"])
        self.assertEqual(result["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
