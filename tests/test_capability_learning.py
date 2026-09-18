import json
import tempfile
import unittest
from pathlib import Path

from learning.capability_learning import CapabilityLearningEngine


class FakeGate:
    def bypass(self):
        from contextlib import nullcontext
        return nullcontext()
    def request(self, *args, **kwargs):
        return None


class FakeEvents:
    def __init__(self): self.rows=[]
    def emit(self, name, data=None): self.rows.append((name, data))


class FakeTasks:
    def __init__(self): self.n=0; self.rows={}
    def transition(self, task_id, status, reason=""):
        self.rows[task_id]=status


class FakeActions:
    class A:
        def __init__(self, result): self.result=result
    def __init__(self): self.calls=[]
    def execute(self, task_id, name, expected):
        self.calls.append((task_id,name,expected))
        return self.A({"tool":name,"verified_payload":True})


class FakeSkills:
    def __init__(self): self.rows=[]
    def upsert(self, **kwargs):
        self.rows.append(kwargs); return kwargs


class FakeRuntime:
    def __init__(self, root):
        self.root=Path(root); self.learning_gate=FakeGate(); self.events=FakeEvents()
        self.tasks=FakeTasks(); self.actions=FakeActions(); self.skills=FakeSkills()
        self._n=0
    def create_task(self, description):
        self._n += 1; tid=f"task-{self._n}"; self.tasks.rows[tid]='ready'; return {"task_id":tid}


class CapabilityLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.runtime=FakeRuntime(self.tmp.name)
        self.engine=CapabilityLearningEngine(self.runtime)

    def tearDown(self): self.tmp.cleanup()

    def proposal(self):
        return {"topic":"python programming fundamentals","confidence":.8,
                "proposal_id":"tk-test","agreements":[{"claim":"Python can be tested incrementally."}]}

    def test_verified_experiment_promotes_skill_after_transfer(self):
        result=self.engine.learn_from_proposal(self.proposal())
        self.assertTrue(result["ok"])
        self.assertTrue(result["transfer_verified"])
        self.assertEqual(len(self.runtime.skills.rows), 1)
        self.assertEqual(self.engine.status()["skills_promoted"], 1)

    def test_untrusted_proposal_does_not_execute(self):
        result=self.engine.learn_from_proposal({"topic":"x","confidence":.2,"agreements":[]})
        self.assertFalse(result["ok"])
        self.assertEqual(self.runtime.actions.calls, [])

    def test_duplicate_skill_uses_stable_id(self):
        a=self.engine.learn_from_proposal(self.proposal())
        b=self.engine.learn_from_proposal(self.proposal())
        self.assertEqual(a["skill"]["skill_id"], b["skill"]["skill_id"])

    def test_state_persists(self):
        proposal=self.proposal(); self.engine.learn_from_proposal(proposal)
        other=CapabilityLearningEngine(self.runtime)
        self.assertEqual(other.status()["skills_promoted"], 1)

