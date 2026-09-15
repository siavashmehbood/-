import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from self.roadmap_benchmark import PersianRoadmapBenchmark


class RoadmapMilestoneTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        config = json.loads(source.read_text(encoding='utf-8-sig'))
        config['memory']['db'] = 'data/test.db'
        config['runtime']['event_log'] = 'data/events.jsonl'
        config['runtime']['goals'] = 'data/goals.json'
        root = Path(directory)
        (root / 'data').mkdir()
        (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        return IranRuntime(root)

    def test_benchmark_cases_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            result = PersianRoadmapBenchmark().run(runtime)
            self.assertGreaterEqual(result.score, .75)
            self.assertGreaterEqual(len(result.cases), 8)
            runtime.close()

    def test_unresolved_reference_is_clarified(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            answer = runtime.handle('همون قبلی رو ادامه بده.')
            self.assertTrue('موضوع' in answer or 'مرجع' in answer)
            runtime.close()

    def test_strategy_reuse_event_is_available_after_repeated_success(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            for _ in range(2):
                runtime.handle('چطور حافظه را بهتر کنیم؟')
            events = [item['event'] for item in runtime.events.recent(200)]
            self.assertIn('learning_update', events)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
