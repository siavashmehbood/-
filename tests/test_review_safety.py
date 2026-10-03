"""Runtime regressions for the approval/XP/queue failures found in phase 0."""
import json
import shutil
from pathlib import Path
import pytest
from runtime.app import IranRuntime
from integrations.chatgpt_review_worker import ChatGPTReviewWorker

@pytest.fixture
def runtime(tmp_path):
    shutil.copy(Path(__file__).parents[1] / 'config.json', tmp_path)
    r = IranRuntime(tmp_path)
    r.internet_access.enable()
    yield r
    r.close()

def test_web_evidence_never_applies_before_two_approvals(runtime):
    runtime.internet_access.enable()
    runtime.internet_learning.fetch = lambda url: {'url': url, 'title':'X social network', 'text':'X is a social networking service. It was launched in 2006 and was formerly known as Twitter.'}
    before = list(runtime.knowledge.facts)
    result = runtime.internet_learning.learn('X social network', ['https://example.org/x','https://example.net/x'])
    assert not result['auto_learned']
    assert runtime.knowledge.facts == before
    assert result['review']['status'] == 'pending'
    assert runtime.human_learning_pending() == []

def test_feedback_duplicate_cannot_earn_unapproved_xp(runtime):
    for message in ['Ù¾Ø§ÛŒØªØ®Øª Ø§ÛŒØ±Ø§Ù† Ú©Ø¬Ø§Ø³ØªØŸ','Ø¯Ø±Ø³ØªÙ‡'] * 2:
        runtime.handle(message)
    assert runtime.effect_learning.stats()['xp'] == 0
    assert runtime.learning_gate.stats()['approved'] == 0

def test_queue_preserves_new_candidate_during_review(runtime):
    runtime.learning.record('first','answer','one',.9)
    def transport(row):
        runtime.learning.record('second','answer','two',.9)
        runtime.sync_chatgpt_learning_reviews()
        return {'learn':True}
    runtime.chatgpt_review_worker.transport = transport
    runtime.process_one_chatgpt_learning_review()
    rows = json.loads(runtime._chatgpt_review_path().read_text(encoding="utf-8"))
    assert len(rows) == 2

def test_untrusted_validation_payload_cannot_authorize_learning(runtime):
    p = runtime.learning_gate.request('memory.add_lesson', {'goal':'g','lesson':'x','_external_validation':{'decision':'LEARN'}})
    assert not runtime.approve_learning(p['proposal_id'], human_confirmed=True, source='test_human')['ok']
    assert runtime.human_learning_pending() == []

def test_duplicate_outcome_credit_ignores_episode_id(tmp_path):
    from learning.effect_loop import EffectLearningLoop
    from learning.learning_engine import LearningEngine
    loop = EffectLearningLoop(tmp_path/'effect.json', LearningEngine(tmp_path/'learning.json'))
    for episode in ['one','two']:
        loop.evaluate('same','same','same','same',{'verified':True,'score':.9},episode_id=episode)
    assert loop.stats()['xp'] == 1_000_000

def test_reviewer_receives_full_claim_and_provenance(runtime):
    payload = {'subject':'A','predicate':'capital','object':'B','source':'test-source','confidence':.8}
    runtime.learning_gate.request('knowledge.add_fact',payload)
    seen=[]
    runtime.chatgpt_review_worker.transport=lambda row:(seen.append(row) or {'learn':False})
    runtime.process_one_chatgpt_learning_review()
    assert seen[0]['payload'] == payload


def test_waiting_queue_survives_restart_then_resumes_without_duplicate(runtime):
    from providers.reviewer import ProviderManager
    from tests.test_reviewer_providers import FakeProvider
    p = runtime.learning_gate.request('knowledge.add_fact', {'subject':'restart fixture','predicate':'is','object':'blue'})
    runtime.internet_access.disable()
    assert runtime.process_one_chatgpt_learning_review()['state'] == 'WAITING_FOR_REVIEWER'
    runtime.close()
    restored = IranRuntime(runtime.root)
    try:
        a=FakeProvider('offline-fixture',{'learn':True})
        restored.chatgpt_review_worker.manager = ProviderManager(restored.root,{},restored.internet_access,[a])
        assert restored.process_one_chatgpt_learning_review()['reason']=='internet_off'
        assert a.calls==0
        restored.internet_access.enable()
        assert restored.process_one_chatgpt_learning_review()['reason']=='reviewed'
        assert restored.approve_learning(p['proposal_id'], human_confirmed=True, source='test_human')['ok']
        again=restored.learning_gate.request('knowledge.add_fact', {'subject':'restart fixture','predicate':'is','object':'blue'})
        assert again['proposal_id']==p['proposal_id'] and again['status']=='approved'
        restored.process_one_chatgpt_learning_review()
        assert a.calls==1
        assert len(restored.knowledge.query('restart fixture'))==1
        assert restored.effect_learning.stats()['xp']==0
    finally:
        restored.close()


def test_corrupt_review_queue_is_not_replaced_during_sync(runtime):
    from persistence import StateCorruptionError
    p=runtime.knowledge.add_fact('queue fixture','is','blue')
    runtime.sync_chatgpt_learning_reviews()
    path=runtime._chatgpt_review_path()
    path.write_text('{broken')
    path.with_suffix('.json.bak').write_text('{broken backup')
    with pytest.raises(StateCorruptionError):
        runtime.sync_chatgpt_learning_reviews()
    assert path.read_text()=='{broken'
    assert runtime.learning_gate.get(p['proposal_id'])['status']=='pending'


def test_review_counts_use_recovered_queue(runtime):
    from persistence import atomic_write_json
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    p=runtime.knowledge.add_fact('count fixture','is','blue')
    mark_chatgpt_correct(runtime,p['proposal_id'],'fixture only')
    path=runtime._chatgpt_review_path()
    atomic_write_json(path,json.loads(path.read_text()))
    path.write_text('{broken')
    assert runtime.chatgpt_review_status()['human_pending']==1
    assert runtime.human_learning_pending()[0]['proposal_id']==p['proposal_id']


def test_corrupt_worker_cooldown_never_sends_request(runtime):
    runtime.knowledge.add_fact('cooldown fixture','is','blue')
    runtime.sync_chatgpt_learning_reviews()
    worker=runtime.chatgpt_review_worker
    calls=[]
    worker.transport=lambda row: calls.append(row) or {'learn':True}
    worker.state_path.write_text('{broken')
    worker.state_path.with_suffix('.json.bak').write_text('{broken backup')
    result=worker.process_one()
    assert not calls
    assert result['state']=='WAITING_FOR_REVIEWER'
    assert result['reason']=='worker_state_corrupt'
    assert worker.status()['state']=='ERROR'
    assert worker.state_path.read_text()=='{broken'


def test_worker_recovers_cooldown_from_backup(runtime):
    from persistence import atomic_write_json
    runtime.knowledge.add_fact('backup cooldown','is','blue')
    runtime.sync_chatgpt_learning_reviews()
    worker=runtime.chatgpt_review_worker
    worker.clock=lambda:1000
    state={'next_allowed_at':worker._iso(1200)}
    atomic_write_json(worker.state_path,state);atomic_write_json(worker.state_path,state)
    worker.state_path.write_text('{broken')
    calls=[]
    worker.transport=lambda row: calls.append(row) or {'learn':True}
    assert worker.process_one()['reason']=='cooldown'
    assert not calls
    assert worker.status()['cooldown_seconds']==200


def test_learning_tick_auto_reviews_online_candidate_then_waits_for_human(runtime):
    holder = {}
    states = []

    runtime.self_directed_learning.prioritize = lambda limit: [{
        "goal": {
            "goal_id": "online-goal-1",
            "topic": "online review fixture",
            "status": "needs_evidence",
            "attempts": 0,
        }
    }]
    runtime.internet_learning.discover = lambda topic: [{"url": "https://example.org"}]

    def fake_learn(topic):
        proposal = runtime.learning_gate.request(
            "memory.add_lesson",
            {"goal": topic, "lesson": "reviewed but not human approved", "confidence": .9},
            "online learning fixture",
        )
        holder["proposal"] = proposal
        return {"ok": True, "topic": topic, "review": proposal, "auto_learned": False}

    runtime.learn_from_internet = fake_learn
    runtime.self_directed_learning.update_outcome = lambda goal_id, state, *a, **k: states.append((goal_id, state))
    runtime.chatgpt_review_worker.transport = lambda row: {
        "learn": True,
        "reason": "supported",
        "confidence": .95,
        "corrections": [],
        "provider": "openrouter",
        "model": "fixture:free",
    }

    result = runtime.learning_tick()
    proposal_id = holder["proposal"]["proposal_id"]

    assert result["online_review"]["ok"]
    assert result["online_review"]["learn"] is True
    assert ("online-goal-1", "human_pending") in states
    assert runtime.learning_gate.get(proposal_id)["status"] == "pending"
    pending = runtime.human_learning_pending()
    assert pending and pending[0]["proposal_id"] == proposal_id
    assert runtime.memory.lesson_search("online review fixture", limit=5) == []  # no durable lesson before human approval


def test_late_rejection_cannot_rewrite_approved_gate_or_ledger(runtime):
    from tests.chatgpt_test_helper import mark_chatgpt_correct

    proposal = runtime.knowledge.add_fact(
        "terminal immutability fixture", "is", "approved", source="fixture"
    )
    proposal_id = proposal["proposal_id"]
    mark_chatgpt_correct(runtime, proposal_id, "terminal fixture")

    approved = runtime.approve_learning(
        proposal_id, human_confirmed=True, source="test_terminal_immutability"
    )
    rejected = runtime.reject_learning(proposal_id)

    assert approved["ok"]
    assert rejected["ok"] is False
    assert rejected["reason"] == "proposal_not_pending"
    assert runtime.learning_gate.get(proposal_id)["status"] == "approved"
    review = runtime.chatgpt_learning_review_status(proposal_id)["row"]
    assert review["status"] == "approved"
    assert review["human_decision"] == "approved"
    assert runtime.knowledge.query("terminal immutability fixture")


def test_bulk_rejection_mirrors_one_exact_snapshot_and_leaves_newer_work_pending(
        runtime, monkeypatch):
    proposals = [
        runtime.learning_gate.request(
            "memory.add_lesson",
            {"goal": f"bulk snapshot {index}", "lesson": "unsafe"},
        )
        for index in range(3)
    ]
    expected_ids = [row["proposal_id"] for row in proposals]
    original_sync = runtime.sync_chatgpt_learning_reviews
    calls = []
    injected = {}

    def sync_exact_snapshot(*args, **kwargs):
        calls.append(list(kwargs.get("proposal_ids") or []))
        result = original_sync(*args, **kwargs)
        if not injected:
            injected["proposal"] = runtime.learning_gate.request(
                "memory.add_lesson",
                {"goal": "newer after snapshot", "lesson": "leave pending"},
            )
        return result

    monkeypatch.setattr(runtime, "sync_chatgpt_learning_reviews", sync_exact_snapshot)

    result = runtime.reject_all_learning(3)

    assert result["ok"]
    assert result["rejected"] == 3
    assert result["skipped"] == []
    assert result["remaining"] == 1
    assert len(calls) == 1
    assert set(calls[0]) == set(expected_ids)
    for proposal_id in expected_ids:
        assert runtime.learning_gate.get(proposal_id)["status"] == "rejected"
        review = runtime.chatgpt_learning_review_status(proposal_id)["row"]
        assert review["status"] == "rejected"
        assert review["human_decision"] == "rejected"
    assert runtime.learning_gate.get(
        injected["proposal"]["proposal_id"]
    )["status"] == "pending"


def test_zero_limit_bulk_rejection_does_not_sync_or_decide(runtime, monkeypatch):
    proposal = runtime.learning_gate.request(
        "memory.add_lesson", {"goal": "zero bulk", "lesson": "stay pending"}
    )
    calls = []
    monkeypatch.setattr(
        runtime, "sync_chatgpt_learning_reviews",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = runtime.reject_all_learning(0)

    assert result["ok"]
    assert result["rejected"] == 0
    assert result["skipped"] == []
    assert result["remaining"] == 1
    assert calls == []
    assert runtime.learning_gate.get(proposal["proposal_id"])["status"] == "pending"
