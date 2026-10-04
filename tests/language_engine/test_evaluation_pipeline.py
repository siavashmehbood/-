import tempfile
import unittest
from pathlib import Path

from evaluation.language.dataset_loader import load_dataset, assert_disjoint_splits
from evaluation.language.gap_map import build_gap_map
from evaluation.language.runner import BenchmarkRunner
from language_engine import IranLanguageEngine
from language_engine.backends import FixtureBackend


class LanguageEvaluationPipelineTests(unittest.TestCase):
    def test_smoke_dataset_runs_offline(self):
        root = Path(__file__).resolve().parents[2]
        cases = load_dataset(root / "evaluation/language/datasets/dev/smoke.json")
        engine = IranLanguageEngine(FixtureBackend({"سلام": "سلام", "Reply with OK": "OK"}))
        rows = BenchmarkRunner(engine).run(cases)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["score"] == 100 for row in rows))

    def test_split_leakage_is_rejected(self):
        root = Path(__file__).resolve().parents[2]
        cases = load_dataset(root / "evaluation/language/datasets/dev/smoke.json")
        with self.assertRaises(ValueError):
            assert_disjoint_splits(("dev", cases), ("hidden", cases))

    def test_gap_map_identifies_winner_and_weak_bucket(self):
        rows = [
            {"model":"a","language":"fa","category":"conversation","score":90},
            {"model":"b","language":"fa","category":"conversation","score":70},
            {"model":"a","language":"tr","category":"reasoning","score":50},
            {"model":"b","language":"tr","category":"reasoning","score":55},
        ]
        gaps = build_gap_map(rows)
        self.assertEqual(gaps["fa:conversation"]["winners"], ["a"])
        self.assertTrue(gaps["tr:reasoning"]["all_weak"])


if __name__ == "__main__":
    unittest.main()
