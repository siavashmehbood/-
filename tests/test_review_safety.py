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
    for message in ['پایتخت ایران کجاست؟','درسته'] * 2:
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
    rows = json.loads(runtime._chatgpt_review_path().read_text())
    assert len(rows) == 2

def test_untrusted_validation_payload_cannot_authorize_learning(runtime):
    p = runtime.learning_gate.request('memory.add_lesson', {'goal':'g','lesson':'x','_external_validation':{'decision':'LEARN'}})
    assert not runtime.approve_learning(p['proposal_id'])['ok']
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
        assert restored.approve_learning(p['proposal_id'])['ok']
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
