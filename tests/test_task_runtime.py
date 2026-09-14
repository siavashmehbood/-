import json
import tempfile
import unittest
from pathlib import Path

from runtime.task_runtime import TaskRuntime, TaskStatus


class TaskRuntimeTests(unittest.TestCase):
    def test_task_lifecycle_persists_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskRuntime(Path(tmp) / 'tasks.json')
            task = runtime.create('build component', goal_id='g1',
                                  expected_result='component works')
            self.assertEqual(task.status, TaskStatus.CREATED)
            runtime.transition(task.task_id, 'ready')
            runtime.transition(task.task_id, 'running')
            self.assertEqual(runtime.get(task.task_id)['attempts'], 1)
            runtime.transition(task.task_id, 'failed', 'verification failed')
            runtime.transition(task.task_id, 'replanning', 'choose another strategy')
            item = runtime.get(task.task_id)
            self.assertEqual(item['status'], 'replanning')
            self.assertEqual(len(item['history']), 4)

    def test_invalid_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = TaskRuntime(Path(tmp) / 'tasks.json')
            task = runtime.create('x')
            with self.assertRaises(ValueError):
                runtime.transition(task.task_id, 'unknown')


if __name__ == '__main__':
    unittest.main()
