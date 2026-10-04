import unittest

from language_engine import GenerationRequest, IranLanguageEngine
from language_engine.backends import FixtureBackend
from evaluation.language.schema import BenchmarkCase
from evaluation.language.selection_gate import SelectionGate


class LanguageEngineFoundationTests(unittest.TestCase):
    def test_fixture_backend_is_offline_and_vendor_neutral(self):
        engine = IranLanguageEngine(FixtureBackend({"سلام": "سلام، چطور می‌تونم کمک کنم؟"}))
        result = engine.generate(GenerationRequest([{"role": "user", "content": "سلام"}], language="fa"))
        self.assertIn("سلام", result.text)
        self.assertTrue(result.metadata["offline"])
        self.assertEqual(engine.identity["backend"], "fixture")

    def test_benchmark_schema_rejects_invalid_tier(self):
        case = BenchmarkCase("x", "fa", "unknown", "conversation", "hard",
                             [{"role": "user", "content": "سلام"}])
        with self.assertRaises(ValueError):
            case.validate()

    def test_selection_gate_accepts_preserved_multilingual_candidate(self):
        languages = {code: 80.0 for code in (
            "en","ar","tr","fr","de","es","pt","ru","zh","ja","ko","hi","ur","it",
            "id","nl","pl","uk","he")}
        candidate = {"persian": 86, "languages": languages, "reasoning": 82,
                     "code": 80, "instruction": 85, "iran_regressions": 0,
                     "one_brain": True, "offline": True, "hidden_gate": True}
        baseline = {"languages": {k: 81 for k in languages},
                    "reasoning": 83, "code": 81, "instruction": 86}
        self.assertTrue(SelectionGate().evaluate(candidate, baseline)["passed"])

    def test_selection_gate_rejects_persian_gain_with_multilingual_loss(self):
        languages = {code: 70.0 for code in (
            "en","ar","tr","fr","de","es","pt","ru","zh","ja","ko","hi","ur","it",
            "id","nl","pl","uk","he")}
        candidate = {"persian": 95, "languages": languages, "reasoning": 80,
                     "code": 80, "instruction": 80}
        baseline = {"languages": {k: 80 for k in languages}}
        result = SelectionGate().evaluate(candidate, baseline)
        self.assertFalse(result["passed"])
        self.assertIn("multilingual_regression_gt_3", result["reasons"])


if __name__ == "__main__":
    unittest.main()
