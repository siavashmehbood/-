import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from self.scenario_benchmark import PersianScenarioBenchmark


class ScenarioBenchmarkTests(unittest.TestCase):
    def make_runtime(self, directory):
        source=Path(__file__).resolve().parents[1]/'config.json'
        config=json.loads(source.read_text(encoding='utf-8-sig'))
        config['memory']['db']='data/m.db'; config['runtime']['event_log']='data/e.jsonl'; config['runtime']['goals']='data/g.json'
        root=Path(directory); (root/'data').mkdir(); (root/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
        return IranRuntime(root)

    def test_benchmark_has_100_categorized_scenarios(self):
        cases=PersianScenarioBenchmark().scenarios()
        self.assertEqual(len(cases), 100)
        self.assertGreaterEqual(len({case.category for case in cases}), 8)

    def test_benchmark_runs_and_returns_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=self.make_runtime(directory)
            result=runtime.scenario_benchmark(limit=12)
            self.assertEqual(len(result.results), 12)
            self.assertIn('factual', result.metrics)
            self.assertGreaterEqual(result.score, .5)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
