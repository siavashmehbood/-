import tempfile
import unittest
from pathlib import Path

from memory.store import Memory
from planning.planner import Planner
from providers.iran import IranProvider
from tools.builtin import build_registry


class IranCoreTests(unittest.TestCase):
    def test_planner(self):
        plan = Planner().build('build a plan')
        self.assertEqual(plan.status, 'ready')
        self.assertEqual(len(plan.steps), 5)
        self.assertIn('تعریف', plan.steps[0].title)

    def test_memory_and_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = Memory(Path(tmp) / 'm.db')
            memory.add('user', 'hello iran')
            self.assertTrue(memory.search('iran'))
            tools = build_registry(tmp, memory)
            self.assertTrue(tools.get('time_now').run())
            self.assertTrue(tools.get('project_summary').run()['files'] >= 1)
            memory.close()

    def test_local_provider(self):
        provider = IranProvider()
        answer = provider.generate([{'role': 'user', 'content': 'سلام ایران'}])
        self.assertIn('ایران', answer)
        self.assertTrue(provider.health()['ok'])

    def test_auto_tool_and_goal(self):
        from core.orchestrator import Orchestrator
        from runtime.events import EventLog
        from runtime.goals import GoalStore
        from security.policy import SecurityPolicy
        with tempfile.TemporaryDirectory() as tmp:
            memory = Memory(Path(tmp) / 'm.db')
            events = EventLog(Path(tmp) / 'events.jsonl')
            goals = GoalStore(Path(tmp) / 'goals.json')
            config = {'security': {'safe_mode': True, 'allow_shell': False, 'allow_network_tools': True}}
            registry = build_registry(tmp, memory)
            agent = type('A', (), {'respond': lambda self, text: 'ok'})()
            orch = Orchestrator(agent, memory, events, registry, SecurityPolicy(config), goals)
            self.assertIn('زمان سیستم', orch.handle('ساعت را بگو'))
            item = goals.add('test goal')
            done = orch.handle('/complete ' + str(item['id']))
            self.assertIn('completed', done)
            memory.close()

    def test_memory_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'persist.db'
            first = Memory(db)
            first.add('user', 'این یک خاطره آزمایشی است')
            first.close()
            second = Memory(db)
            rows = second.search('خاطره آزمایشی')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], 'user')
            second.close()

    def test_safe_mode_blocks_write(self):
        from security.policy import SecurityPolicy
        policy = SecurityPolicy({'security': {'safe_mode': True, 'allow_shell': True, 'allow_network_tools': False}})
        self.assertTrue(policy.allows('read'))
        self.assertFalse(policy.allows('write'))
        self.assertFalse(policy.allows('shell'))
        self.assertFalse(policy.allows('deploy'))
        self.assertFalse(policy.allows('network'))

    def test_network_policy(self):
        from security.policy import SecurityPolicy
        self.assertTrue(SecurityPolicy({'security': {'allow_network_tools': True}}).allows('network'))
        self.assertFalse(SecurityPolicy({'security': {'allow_network_tools': False}}).allows('network'))

    def test_provider_handles_empty_input(self):
        self.assertTrue(IranProvider().generate([]))

    def test_tool_router(self):
        from core.tool_router import ToolRouter
        router = ToolRouter()
        self.assertEqual(router.choose('ساعت الان چند است')[0], 'time_now')
        self.assertEqual(router.choose('مشخصات سیستم')[0], 'system_info')

    def test_path_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = Memory(Path(tmp) / 'm.db')
            tools = build_registry(tmp, memory)
            with self.assertRaises(PermissionError):
                tools.get('read_project_file').run(path='../secret.txt')
            memory.close()

    def test_note_permission(self):
        from security.policy import SecurityPolicy
        policy = SecurityPolicy({'security': {'safe_mode': True, 'allow_network_tools': True}})
        self.assertFalse(policy.allows('write'))
        self.assertTrue(policy.allows('network'))


if __name__ == '__main__':
    unittest.main()

