import unittest
from evaluation.language.schema import BenchmarkCase
from evaluation.language.scorer import DeterministicScorer
from evaluation.language.blind_judge import apply_judgments
from evaluation.language.selection_score import weighted_score


class ScoringIntegrityTests(unittest.TestCase):
    def test_rubric_only_naturalness_never_auto_passes(self):
        case=BenchmarkCase("natural","fa","persian","conversation","hard",
            [{"role":"user","content":"طبیعی جواب بده"}],rubric=("طبیعی باشد",)).validate()
        result=DeterministicScorer().score(case,"هر متن غیرخالی")
        self.assertIsNone(result["score"])
        self.assertTrue(result["requires_judge"])

    def test_blind_judgment_fills_pending_score(self):
        rows=[{"case_id":"x","score":None}]
        result=apply_judgments(rows,{"x":{"score":82,"judge":"blind-a","reason":"rubric"}})
        self.assertEqual(result[0]["score"],82)

    def test_weight_formula_sums_to_100_percent(self):
        metrics={"persian":100,"multilingual":100,"reasoning_knowledge":100,
                 "context_instruction":100,"code":100,"tool_agent":100,"safety":100}
        self.assertEqual(weighted_score(metrics),100)


if __name__=="__main__":
    unittest.main()
