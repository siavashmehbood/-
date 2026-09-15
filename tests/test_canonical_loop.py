import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class CanonicalLoopTests(unittest.TestCase):
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

    def test_natural_turn_runs_canonical_cognitive_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            answer = runtime.handle('برای پروژه معماری شناختی ایران یک برنامه امن طراحی کن.')
            self.assertTrue(answer)
            events = [item['event'] for item in runtime.events.recent(200)]
            for event in ('runtime_ready', 'language_analysis', 'cognitive_cycle', 'plan_created',
                          'reflection', 'learning_update', 'response_generated'):
                self.assertIn(event, events)
            snapshot = runtime.cognitive_snapshot('معماری شناختی ایران')
            self.assertIn('world', snapshot)
            self.assertIn('memory', snapshot)
            self.assertIn('learning', snapshot)
            self.assertIn('prediction', snapshot)
            self.assertGreaterEqual(snapshot['learning']['experiences'], 1)
            self.assertGreaterEqual(snapshot['world']['observations'], 1)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
