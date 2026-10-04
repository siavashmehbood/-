import unittest
from pathlib import Path
from evaluation.language.dataset_loader import load_dataset
from evaluation.language.validator import TIER1, validate_suite
from evaluation.language.reports import summarize


class SuiteValidatorTests(unittest.TestCase):
    def test_public_smoke_has_exact_tier1_language_set(self):
        root=Path(__file__).resolve().parents[2]
        cases=load_dataset(root/"evaluation/language/datasets/public_eval/tier1_smoke.json")
        result=validate_suite(cases,require_all_languages=True)
        self.assertTrue(result["passed"],result["errors"])
        self.assertEqual(result["languages"],20)
        self.assertEqual(set(result["counts"]),set(TIER1))

    def test_report_keeps_per_language_scores(self):
        rows=[{"language":"fa","category":"conversation","score":90,"latency_ms":2},
              {"language":"en","category":"instruction","score":80,"latency_ms":4}]
        report=summarize(rows)
        self.assertEqual(report["languages"]["fa"],90)
        self.assertEqual(report["languages"]["en"],80)
        self.assertEqual(report["overall"],85)


if __name__=="__main__":
    unittest.main()
