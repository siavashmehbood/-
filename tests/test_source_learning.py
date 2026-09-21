import json
import shutil
from pathlib import Path
from learning.trusted_knowledge import TrustedKnowledgeBootstrap
from learning.self_directed import SelfDirectedLearning
from runtime.app import IranRuntime
from tests.chatgpt_test_helper import mark_chatgpt_correct

def sources(a,b=None):
    return [{'url':'https://one.example.org/doc','title':'NOVA star','text':a,'confidence':.9,'retrieved_at':'2026-01-01','source_type':'documentation'},
            {'url':'https://two.example.net/api','title':'NOVA star','text':b or a,'confidence':.9,'retrieved_at':'2026-01-02','source_type':'structured_api'}]

def test_conflicting_numbers_do_not_become_agreement():
    result=TrustedKnowledgeBootstrap().build('NOVA star',sources('NOVA star has a measured radius of 100 units.','NOVA star has a measured radius of 200 units.'))
    assert result['conflicts'] and not result['agreements']
    assert result['status']=='needs_review'

def test_subdomains_are_not_independent():
    rows=sources('NOVA star has a measured radius of 100 units.')
    rows[1]['url']='https://two.example.org/api'
    result=TrustedKnowledgeBootstrap().build('NOVA star',rows)
    assert 'sources_not_independent' in result['issues']
    assert result['agreements']==[]

def test_provenance_survives_and_retrieval_time_does_not_change_identity():
    rows=sources('NOVA star has a measured radius of 100 units.')
    a=TrustedKnowledgeBootstrap().build('NOVA star',rows)
    rows[0]['retrieved_at']='2026-02-01'
    b=TrustedKnowledgeBootstrap().build('NOVA star',rows)
    assert a['proposal_id']==b['proposal_id']
    assert b['sources'][0]['retrieved_at']=='2026-02-01'
    assert b['sources'][0]['source_type']=='documentation'

def test_curriculum_stages_require_distinct_verified_assessments(tmp_path):
    s=SelfDirectedLearning(tmp_path/'goals.json')
    goal=s.next_curriculum_goals(['astronomy'],1)[0]
    assert len(s.next_curriculum_goals(['astronomy'],1))==1
    s.record_assessment(goal['goal_id'],'failed',.2,False)
    assert s.goals[0].stage=='foundation'
    s.record_assessment(goal['goal_id'],'e1',.9,True)
    s.record_assessment(goal['goal_id'],'e1',.9,True)
    assert s.goals[0].stage=='intermediate'
    restored=SelfDirectedLearning(tmp_path/'goals.json')
    assert restored.goals[0].stage=='intermediate'

def test_gap_and_duplicate_evidence_are_not_reviewer_spam(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    for _ in range(4): r.handle('درباره ستاره زرتاکس نادیده چه میدانی؟')
    assert len(r.self_directed_learning.goals)<5
    assert not r.human_learning_pending()
    r.close()

def test_online_claim_needs_review_and_human_then_is_reused(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path);r.internet_access.enable()
    claim='ستاره نوا یک ستاره آزمایشی با رنگ آبی روشن است.'
    evidence=sources(claim)
    for item in evidence:item['title']='ستاره نوا'
    bundle=r.trusted_knowledge.build('ستاره نوا',evidence)
    assert bundle['status']=='ready_for_review'
    p=r.learning_gate.request('trusted_knowledge.bootstrap',bundle)
    assert r.knowledge.query('ستاره نوا')==[]
    mark_chatgpt_correct(r,p['proposal_id'],'fixture corroborated')
    assert r.approve_learning(p['proposal_id'])['ok']
    assert r.effect_learning.stats()['xp']==0
    answer=r.handle('ستاره نوا چیست؟')
    assert claim in answer
    assert r.effect_learning.stats()['xp']==1_000_000
    r.handle('ستاره نوا چیست؟')
    assert r.effect_learning.stats()['xp']==1_000_000
    r.close();r=IranRuntime(tmp_path)
    assert claim in r.handle('ستاره نوا چیست؟')
    assert r.effect_learning.stats()['xp']==1_000_000
    r.close()


def test_retrieving_many_claims_is_not_curriculum_mastery(tmp_path):
    path=tmp_path/'goals.json';learner=SelfDirectedLearning(path)
    goal=learner.next_curriculum_goals(['astronomy'],1)[0]
    for i in range(12):
        learner.record_assessment(goal['goal_id'],f'claim-{i}',.9,True,kind='retrieval')
    restored=SelfDirectedLearning(path)
    assert restored.goals[0].stage=='foundation'
    assert restored.goals[0].status!='consolidated'
    assert len(restored.goals[0].assessments)==12
    restored.record_assessment(goal['goal_id'],'claim-0',.9,True,kind='retrieval')
    assert len(restored.goals[0].assessments)==12
    restored.record_assessment(goal['goal_id'],'held-out-task',.9,True,kind='evaluation')
    assert restored.goals[0].stage=='intermediate'


def test_runtime_claim_reuse_records_retrieval_without_promoting_goal(tmp_path):
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    r=IranRuntime(tmp_path)
    goal=r.self_directed_learning.create_goal('ستاره نوا','missing_knowledge','understand the star','medium','astronomy')
    claim='ستاره نوا یک ستاره آزمایشی با رنگ آبی روشن است.'
    evidence=sources(claim)
    for item in evidence:item['title']='ستاره نوا'
    bundle=r.trusted_knowledge.build('ستاره نوا',evidence)
    p=r.learning_gate.request('trusted_knowledge.bootstrap',bundle)
    mark_chatgpt_correct(r,p['proposal_id'],'fixture')
    assert r.approve_learning(p['proposal_id'])['ok']
    assert claim in r.handle('ستاره نوا چیست؟')
    current=next(g for g in r.self_directed_learning.goals if g.goal_id==goal['goal_id'])
    assert current.stage=='foundation'
    assert current.assessments[0]['kind']=='retrieval'
    assert r.effect_learning.stats()['xp']==1_000_000
    r.close()
