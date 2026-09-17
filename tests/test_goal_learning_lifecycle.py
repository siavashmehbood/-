import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool


class GoalLearningLifecycleTests(unittest.TestCase):
    def test_goal_persists_evidence_outcome_and_learning(self):
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
            runtime.registry.register(Tool('good_action', 'good', lambda: 'correct', safe=True))
            try:
                result = runtime.execute_verified_goal('lifecycle demo', 'good_action', None, 'correct')
                goal = result['goal']
                self.assertEqual(goal['status'], 'completed')
                self.assertEqual(goal['attempts'], 1)
                self.assertTrue(goal['evidence'])
                self.assertTrue(goal['outcome']['success'])
                self.assertTrue(goal['learning'])
                events = [e for e in runtime.events.recent(100) if e.get('event') == 'goal_outcome']
                self.assertTrue(events)
                self.assertTrue(events[-1]['data']['success'])
            finally:
                runtime.close()


if __name__ == '__main__':
    unittest.main()
