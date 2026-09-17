import tempfile
import unittest
from pathlib import Path

from runtime.events import EventLog
from runtime.task_runtime import TaskRuntime, TaskStatus
from core.action_runtime import ActionExecutor
from core.observation import ObservationEngine
from core.verification import VerificationEngine
from core.failure import FailureIntelligence
from core.replanning import Replanner
from tools.registry import ToolRegistry, Tool


class AllowPolicy:
    def allows(self, permission):
        return permission == 'read'


class ActionLoopTests(unittest.TestCase):
    def test_action_requires_observed_evidence_for_success(self):
        with tempfile.TemporaryDirectory() as d:
            events = EventLog(Path(d) / 'events.jsonl')
            registry = ToolRegistry()
            registry.register(Tool('echo_test', 'test', lambda value='ok': value, safe=True))
            action = ActionExecutor(registry, AllowPolicy(), events)
            observer = ObservationEngine(events)
            verifier = VerificationEngine(events)
            a = action.execute('task-1', 'echo_test', 'value observed', value='ok')
            o = observer.observe(a, evidence=['tool-result'])
            v = verifier.verify(o)
            self.assertTrue(v.success)
            self.assertEqual(v.action_id, a.action_id)

    def test_recovery_verification_rejects_wrong_alternative_result(self):
        with tempfile.TemporaryDirectory() as d:
            events = EventLog(Path(d) / 'events.jsonl')
            registry = ToolRegistry()
            registry.register(Tool('primary_wrong', 'test', lambda: 'wrong', safe=True))
            registry.register(Tool('alternative_wrong', 'test', lambda: 'still wrong', safe=True))
            action = ActionExecutor(registry, AllowPolicy(), events)
            observer = ObservationEngine(events)
            verifier = VerificationEngine(events)
            primary = action.execute('task-3', 'primary_wrong', 'correct')
            primary_obs = observer.observe(primary, evidence=[])
            primary_v = verifier.verify(primary_obs, predicate=lambda obs: bool(obs.evidence) and str(obs.expected).lower() in str(obs.actual).lower())
            self.assertFalse(primary_v.success)
            alt = action.execute('task-3', 'alternative_wrong', 'correct')
            alt_obs = observer.observe(alt, evidence=[{'source': 'independent-recheck'}])
            alt_v = verifier.verify(alt_obs, predicate=lambda obs: bool(obs.evidence) and str(obs.expected).lower() in str(obs.actual).lower())
            self.assertFalse(alt_v.success)


    def test_task_rejects_invalid_transition(self):
        with tempfile.TemporaryDirectory() as d:
            rt = TaskRuntime(Path(d) / 'tasks.json')
            task = rt.create('demo')
            with self.assertRaises(ValueError):
                rt.transition(task.task_id, TaskStatus.SUCCESS.value, 'skip execution')
            rt.transition(task.task_id, TaskStatus.READY.value)
            rt.transition(task.task_id, TaskStatus.RUNNING.value)
            rt.transition(task.task_id, TaskStatus.REPLANNING.value, 'failed assumption')
            self.assertEqual(rt.get(task.task_id)['status'], TaskStatus.REPLANNING.value)

    def test_failure_produces_replan_decision(self):
        with tempfile.TemporaryDirectory() as d:
            events = EventLog(Path(d) / 'events.jsonl')
            diagnosis = FailureIntelligence().diagnose(
                'unexpected result', 'verification', 'expected file')
            decision = Replanner(events).replan(
                'task-2', diagnosis.reason, diagnosis.failed_assumption,
                ['inspect state', 'choose alternative'])
            self.assertEqual(diagnosis.category, 'verification_failure')
            self.assertEqual(decision.selected, 'inspect state')
            self.assertEqual(events.recent(1)[0]['event'], 'replan_triggered')


if __name__ == '__main__':
    unittest.main()
