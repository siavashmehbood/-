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
    def __init__(self): self.calls=[]; self.fail=False
    def execute(self, task_id, name, expected, **kwargs):
        self.calls.append((task_id,name,expected))
        if self.fail:
            return self.A({"ok": False, "returncode": 1, "stdout": "", "stderr": "assertion failed"})
        return self.A({"ok": True, "returncode": 0, "stdout": "verified", "stderr": ""})


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

    def test_untrusted_internet_proposal_is_not_experimented(self):
        class Internet:
            def learn(self, topic, auto=True):
                return {"proposal": internet.proposal, "auto_learned": False}
        internet = Internet()
        internet.proposal = self.proposal()
        self.runtime.internet_learning = internet
        result = self.engine.learn_topic("python programming fundamentals", auto=True)
        self.assertFalse(result["capability"]["ok"])
        self.assertEqual(result["capability"]["reason"], "internet_evidence_not_auto_trusted")
        self.assertEqual(self.runtime.actions.calls, [])

    def test_state_persists(self):
        proposal=self.proposal(); self.engine.learn_from_proposal(proposal)
        other=CapabilityLearningEngine(self.runtime)
        self.assertEqual(other.status()["skills_promoted"], 1)

    def test_generic_claim_experiment_does_not_require_topic_template(self):
        proposal={"topic":"novel capability domain","confidence":.8,
                  "proposal_id":"novel-1","agreements":[{"claim":"A deterministic invariant can be checked locally."}]}
        result=self.engine.learn_from_proposal(proposal)
        self.assertTrue(result["ok"])
        self.assertEqual(result["experiment"]["steps"][0]["test"], "claim_repeatability")

    def test_failed_experiment_persists_structured_diagnosis(self):
        self.runtime.actions.fail=True
        result=self.engine.learn_from_proposal(self.proposal())
        self.assertFalse(result["ok"])
        failure=self.engine.status()["failure_history"][-1]
        for key in ("failure_type", "failure_stage", "evidence", "observed_output",
                    "expected_output", "likely_cause", "repair_candidates"):
            self.assertIn(key, failure)
