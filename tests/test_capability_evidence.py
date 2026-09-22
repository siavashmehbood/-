from learning.capability_learning import CapabilityLearningEngine
from tests.test_capability_learning import FakeRuntime, FakeActions
from tools.builtin import build_registry


def proposal(topic='novel astronomy'):
    return {'topic':topic,'confidence':.8,'proposal_id':'fixture',
            'agreements':[{'claim':'Unverified domain claim.'}]}


def test_generic_smoke_test_cannot_promote_domain_knowledge(tmp_path):
    runtime=FakeRuntime(tmp_path)
    result=CapabilityLearningEngine(runtime).learn_from_proposal(proposal())
    assert result.get('verification_scope')=='diagnostic_only'
    assert result.get('claim_verified') is False
    assert not result.get('transfer_verified')
    assert runtime.skills.rows==[]


def test_promoted_procedure_retains_executable_artifact_not_claim(tmp_path):
    runtime=FakeRuntime(tmp_path)
    result=CapabilityLearningEngine(runtime).learn_from_proposal(proposal('python programming fundamentals'))
    skill=result['skill']
    assert skill['procedure']['steps'][0].get('code')
    assert 'Unverified domain claim.' not in skill['goal_patterns']
    assert skill['procedure'].get('claim_verified') is False


def test_transfer_executes_the_actual_procedure_and_rejects_overfit(tmp_path):
    import pytest
    pytest.importorskip('resource')
    runtime=FakeRuntime(tmp_path)
    engine=CapabilityLearningEngine(runtime)
    result=engine.learn_from_proposal(proposal('python programming fundamentals'))
    skill=result['skill']
    # Fits the original training example (2,4), fails unseen inputs.
    skill['procedure']['steps'][0]['code']='def add(a,b):\n    return 6'
    registry=build_registry(tmp_path,None)
    class RealActions:
        def execute(self,task,name,expected,**kwargs):
            return FakeActions.A(registry.run(name,**kwargs))
    runtime.actions=RealActions()
    assert not engine._transfer(skill)


def test_real_artifact_requires_reviews_and_reuses_after_restart(tmp_path):
    import pytest
    pytest.importorskip('resource')
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime
    from tests.chatgpt_test_helper import mark_chatgpt_correct
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    result=r.capability_learning.learn_from_proposal(proposal('python programming fundamentals'))
    assert result['pending_approval'] and result['transfer_verified']
    pid=result['proposal']['proposal_id'];sid=result['skill']['skill_id']
    assert not any(row.get('skill_id')==sid for row in r.skills.skills)
    assert not r.approve_learning(pid)['ok']
    mark_chatgpt_correct(r,pid,'fixture only')
    assert r.approve_learning(pid)['ok']
    r.close()
    r=IranRuntime(tmp_path)
    skill=next(row for row in r.skills.skills if row['skill_id']==sid)
    code=skill['procedure']['steps'][0]['code']+'\nprint(add(100, -8))'
    output=r.registry.run('sandbox_python',code=code)
    assert output['ok'] and output['stdout'].strip().endswith('92')
    assert r.effect_learning.stats()['xp']==0
    assert not skill['procedure']['claim_verified']
    r.close()
