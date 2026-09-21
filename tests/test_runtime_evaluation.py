import shutil
from pathlib import Path
import pytest
from runtime.app import IranRuntime
from core.semantic_verifier import VerificationResult

@pytest.mark.parametrize('question', ['اسم من چیست؟', 'اسم من چیه؟', 'نام من چیست؟', 'اسمم چی بود؟'])
def test_current_identity_survives_correction_and_restart(tmp_path, question):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r = IranRuntime(tmp_path)
    assert 'UNKNOWN' in r.handle(question)
    r.handle('من علی هستم.'); r.handle('من رضا هستم.')
    assert 'رضا' in r.handle(question)
    r.close()
    r = IranRuntime(tmp_path)
    assert 'رضا' in r.handle(question)
    r.close()


def test_short_route_calls_actual_verifier(tmp_path, monkeypatch):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r = IranRuntime(tmp_path)
    calls = []
    def reject(question, answer, *args, **kwargs):
        calls.append((question,answer))
        return VerificationResult(False, .1, ['fixture_failed_consistency'], [])
    monkeypatch.setattr(r.cognitive_system.pipeline.semantic_verifier, 'verify', reject)
    assert 'UNKNOWN' in r.handle('سلام')
    assert any(row[0] == 'assistant' and 'UNKNOWN' in row[1] for row in r.memory.recent(10))
    assert calls and r.cognitive_system.last_trace.verification_status == 'UNKNOWN'
    assert 'fixture_failed_consistency' in r.cognitive_system.last_trace.verification_reasons
    r.close()


def test_role_statement_does_not_replace_personal_name(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json', tmp_path)
    r=IranRuntime(tmp_path)
    r.handle('من علی هستم.'); r.handle('من دانشجو هستم.')
    assert 'علی' in r.handle('اسم من چیست؟')
    assert all(f['object']!='دانشجو' for f in r.user_model.facts(predicate='name'))
    assert any(f['object']=='دانشجو' for f in r.user_model.facts(predicate='role'))
    r.close()


@pytest.mark.parametrize('prior', ['REPAIR', 'CLARIFY', 'UNKNOWN'])
def test_final_consistency_check_cannot_erase_prior_failure(tmp_path, monkeypatch, prior):
    from core.cognitive_pipeline import TurnTrace
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    def candidate(text):
        r.dialogue.last_trace=TurnTrace(user_text=text,verification_status=prior,
            verification_reasons=['missing_required_evidence'],confidence=.4)
        return 'پایتخت ایران تهران است.'
    monkeypatch.setattr(r.cognitive_system.pipeline,'run',candidate)
    r.handle('پایتخت ایران کجاست؟')
    assert r.cognitive_system.last_trace.verification_status==prior
    assert 'missing_required_evidence' in r.cognitive_system.last_trace.verification_reasons
    r.close()


def test_unrelated_short_route_rejected_before_memory_commit(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    answer=r.cognitive_system.pipeline._persist_answer('پایتخت ایران کجاست؟','موز یک میوه است.')
    assert answer.startswith('UNKNOWN:')
    assert not any(row[0]=='assistant' and row[1]=='موز یک میوه است.' for row in r.memory.recent(10))
    r.close()


def test_runtime_abstains_on_conflicting_approved_facts(tmp_path):
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    p=r.learning_gate.request('knowledge.add_fact',{'subject':'ایران','predicate':'پایتخت','object':'شیراز','source':'conflicting_fixture'})
    mark_chatgpt_correct(r,p['proposal_id'],'fixture only')
    assert r.approve_learning(p['proposal_id'])['ok']
    answer=r.handle('پایتخت ایران کجاست؟')
    assert answer.startswith('UNKNOWN:')
    assert r.cognitive_system.last_trace.evidence_status=='CONFLICTING'
    assert 'conflicting_evidence' in r.cognitive_system.last_trace.verification_reasons
    assert r.effect_learning.stats()['xp']==0
    r.close()
    r=IranRuntime(tmp_path)
    assert r.handle('پایتخت ایران کجاست؟').startswith('UNKNOWN:')
    assert r.cognitive_system.last_trace.evidence_status=='CONFLICTING'
    r.close()


def test_unknown_is_not_logged_as_verified_answer(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    r.cognitive_system.pipeline._persist_answer('پایتخت کشور ناشناخته کجاست؟','UNKNOWN: شواهد کافی ندارم.')
    events=[e for e in r.events.recent(30) if e['event']=='response_generated']
    assert events[-1]['data']['verified'] is False
    assert r.dialogue.last_trace.verification_status=='UNKNOWN'
    r.close()


def test_explicit_knowledge_correction_requires_both_reviews_and_survives_restart(tmp_path):
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    competing=r.knowledge.add_fact('ایران','پایتخت','شیراز',source='fixture')
    mark_chatgpt_correct(r,competing['proposal_id'],'fixture only')
    assert r.approve_learning(competing['proposal_id'])['ok']
    correction=r.knowledge.contradict('ایران','پایتخت','تهران',source='correction_fixture')
    assert correction['kind']=='knowledge.contradict'
    assert not r.approve_learning(correction['proposal_id'])['ok']
    assert r.handle('پایتخت ایران کجاست؟').startswith('UNKNOWN:')
    mark_chatgpt_correct(r,correction['proposal_id'],'fixture only')
    assert r.handle('پایتخت ایران کجاست؟').startswith('UNKNOWN:')
    assert r.approve_learning(correction['proposal_id'])['ok']
    assert 'تهران' in r.handle('پایتخت ایران کجاست؟')
    assert not r.approve_learning(correction['proposal_id'])['ok']
    assert r.effect_learning.stats()['xp']==0
    r.close()
    r=IranRuntime(tmp_path)
    assert 'تهران' in r.handle('پایتخت ایران کجاست؟')
    assert r.cognitive_system.last_trace.evidence_status=='SUPPORTED'
    assert len([f for f in r.knowledge.facts if f['subject']=='ایران' and f['predicate']=='پایتخت'])==2
    r.close()


def test_approved_corroboration_retains_both_sources_without_duplicate_fact(tmp_path):
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    for source in ('reference_a','reference_b'):
        p=r.knowledge.add_fact('ایران','پایتخت','تهران',source=source)
        mark_chatgpt_correct(r,p['proposal_id'],'fixture only')
        assert r.approve_learning(p['proposal_id'])['ok']
    rows=[f for f in r.knowledge.facts if f['subject']=='ایران' and f['predicate']=='پایتخت']
    assert len(rows)==1
    assert {'reference_a','reference_b'} <= {x['source'] for x in rows[0]['source_observations']}
    assert 'تهران' in r.handle('پایتخت ایران کجاست؟')
    assert {'reference_a','reference_b'} <= set(r.cognitive_system.last_trace.evidence_sources)
    assert r.effect_learning.stats()['xp']==0
    r.close()
    r=IranRuntime(tmp_path)
    assert 'تهران' in r.handle('پایتخت ایران کجاست؟')
    assert {'reference_a','reference_b'} <= set(r.cognitive_system.last_trace.evidence_sources)
    assert r.effect_learning.stats()['xp']==0
    r.close()
