import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from runtime.task_runtime import TaskStatus
from tools.registry import Tool


class RecoveryE2ETests(unittest.TestCase):
    def test_failure_replan_alternative_world_prediction(self):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'data').mkdir()
            data = json.loads(source.read_text(encoding='utf-8-sig'))
            data['memory']['db'] = 'data/test.db'
            data['runtime']['event_log'] = 'data/events.jsonl'
            data['runtime']['goals'] = 'data/goals.json'
            (root / 'config.json').write_text(
                json.dumps(data, ensure_ascii=False), encoding='utf-8')
            rt = IranRuntime(root)
            rt.registry.register(Tool('primary_ok', 'primary', lambda: 'wrong', safe=True))
            rt.registry.register(Tool('alternative_ok', 'alternative', lambda: 'correct', safe=True))
            result = rt.execute_recoverable_task(
                'recover demo', 'primary_ok', 'alternative_ok', 'correct')
            self.assertFalse(result['primary']['success'])
            self.assertEqual(result['replan']['selected'], 'alternative_ok')
            self.assertTrue(result['alternative']['success'])
            self.assertEqual(result['task']['status'], TaskStatus.SUCCESS.value)
            self.assertGreaterEqual(len(rt.world.recent_transitions(10)), 2)
            cal = rt.prediction.calibration()
            self.assertEqual(cal['primary_ok']['success_rate'], 0.0)
            self.assertEqual(cal['alternative_ok']['success_rate'], 1.0)
            events = [x['event'] for x in rt.events.recent(40)]
            self.assertIn('failure_diagnosed', events)
            self.assertIn('plan_replanned', events)
            self.assertIn('recovery_completed', events)
            rt.close()


if __name__ == '__main__':
    unittest.main()
