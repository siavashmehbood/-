import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool


class VerifiedNegativeLearningTests(unittest.TestCase):
    def test_verified_failure_becomes_negative_evidence_for_next_decision(self):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            runtime = IranRuntime(root)
            runtime.registry.register(Tool('bad_action', 'bad', lambda: 'wrong', safe=True))
            runtime.registry.register(Tool('good_action', 'good', lambda: 'correct', safe=True))
            try:
                first = runtime.execute_verified_goal(
                    'learn from failure demo', 'bad_action', 'good_action', 'correct')
                self.assertTrue(first['alternative']['success'])
                records = runtime.outcome_learning.retrieve_context('learn from failure demo', 'task', 10)
                bad = [r for r in records if r['action'] == 'bad_action']
                good = [r for r in records if r['action'] == 'good_action']
                self.assertTrue(bad and bad[-1]['verified'] and bad[-1]['score'] == 0.0)
                self.assertTrue(good and good[-1]['verified'] and good[-1]['score'] == 1.0)

                second = runtime.execute_verified_goal(
                    'learn from failure demo', 'bad_action', 'good_action', 'correct')
                self.assertTrue(second['primary']['success'])
                reused = [e for e in runtime.events.recent(200)
                           if e.get('event') == 'strategy_reused'
                           and e.get('data', {}).get('source') == 'outcome_backed_learning']
                self.assertTrue(reused)
                self.assertEqual(reused[-1]['data']['selected'], 'good_action')
            finally:
                runtime.close()


if __name__ == '__main__':
    unittest.main()
