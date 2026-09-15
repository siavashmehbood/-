import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from runtime.task_runtime import TaskStatus
from tools.registry import Tool


class VerifiedExecutionIntegrationTests(unittest.TestCase):
    def _runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / 'config.json'
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        data['memory']['db'] = 'data/test.db'
        data['runtime']['event_log'] = 'data/events.jsonl'
        data['runtime']['goals'] = 'data/goals.json'
        root = Path(directory)
        (root / 'data').mkdir()
        (root / 'config.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return IranRuntime(root)

    def test_public_run_requires_verified_outcome_and_replans(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.registry.register(Tool('primary_wrong', 'primary', lambda: 'wrong', safe=True))
            runtime.registry.register(Tool('alternative_right', 'alternative', lambda: 'correct', safe=True))
            answer = runtime.handle(
                '/run recover demo --tool primary_wrong --expected correct '
                '--alternative alternative_right')
            self.assertIn('task=success', answer)
            self.assertIn('verified=True', answer)
            task = runtime.tasks.get(runtime.tasks._load()[-1]['task_id'])
            self.assertEqual(task['status'], TaskStatus.SUCCESS.value)
            events = [item['event'] for item in runtime.events.recent(80)]
            self.assertIn('action_started', events)
            self.assertIn('observation_created', events)
            self.assertIn('verification_completed', events)
            self.assertIn('replan_triggered', events)
            self.assertIn('verified_task_completed', events)
            runtime.close()

    def test_public_run_does_not_mark_failed_verification_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self._runtime(directory)
            runtime.registry.register(Tool('wrong_only', 'wrong', lambda: 'wrong', safe=True))
            answer = runtime.handle('/run failed demo --tool wrong_only --expected correct')
            self.assertIn('task=failed', answer)
            self.assertIn('verified=False', answer)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
