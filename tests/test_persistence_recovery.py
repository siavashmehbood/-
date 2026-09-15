import json
import tempfile
import unittest
from pathlib import Path

from knowledge.knowledge_graph import KnowledgeGraph
from runtime.goals import GoalStore
from persistence import atomic_write_json, load_json_with_backup
from runtime.task_runtime import TaskRuntime


class PersistenceRecoveryTests(unittest.TestCase):
    def test_atomic_write_creates_backup_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            atomic_write_json(path, {'version': 1})
            atomic_write_json(path, {'version': 2})
            self.assertEqual(json.loads(path.read_text())['version'], 2)
            self.assertEqual(load_json_with_backup(path.with_name('missing.json'), {}), {})
            path.write_text('{broken', encoding='utf-8')
            self.assertEqual(load_json_with_backup(path, {})['version'], 1)

    def test_knowledge_and_goals_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            graph = KnowledgeGraph(root / 'knowledge.json')
            graph.add_fact('ایران', 'پایتخت', 'تهران', .99, 'test')
            goals = GoalStore(root / 'goals.json')
            item = goals.add('تست پایداری')
            restarted_graph = KnowledgeGraph(root / 'knowledge.json')
            restarted_goals = GoalStore(root / 'goals.json')
            self.assertEqual(restarted_graph.best_fact('ایران', 'پایتخت')['object'], 'تهران')
            self.assertEqual(restarted_goals.get if False else restarted_goals.list()[0]['id'], item['id'])

    def test_task_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tasks.json'
            first = TaskRuntime(path)
            task = first.create('کار آزمایشی')
            first.transition(task.task_id, 'ready', 'preconditions met')
            first.transition(task.task_id, 'running', 'started')
            second = TaskRuntime(path)
            self.assertEqual(second.get(task.task_id)['status'], 'running')


if __name__ == '__main__':
    unittest.main()
