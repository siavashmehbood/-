import json
import pytest
from persistence import atomic_write_json, StateCorruptionError
from security.learning_gate import LearningGate
from learning.learning_engine import LearningEngine
from learning.effect_loop import EffectLearningLoop


def test_gate_corruption_does_not_erase_approvals(tmp_path):
    path = tmp_path / 'gate.json'
    gate = LearningGate(path)
    row = gate.request('test', {'claim': 'stable'})
    gate.decide(row['proposal_id'], 'approved')
    atomic_write_json(path, json.loads(path.read_text()))
    path.write_text('{broken')
    recovered = LearningGate(path)
    assert recovered.get(row['proposal_id'])['status'] == 'approved'
    recovered.request('test', {'claim': 'new'})
    assert json.loads(path.with_suffix('.json.bak').read_text())[0]['status'] == 'approved'


@pytest.mark.parametrize('factory', [LearningGate, LearningEngine, lambda p: EffectLearningLoop(p, None)])
def test_unrecoverable_state_fails_closed(tmp_path, factory):
    path = tmp_path / 'state.json'
    path.write_text('{broken')
    with pytest.raises(StateCorruptionError):
        factory(path)
    assert path.read_text() == '{broken'


def test_effect_credit_survives_damaged_primary(tmp_path):
    path = tmp_path / 'effect.json'
    state = {'xp': 1_000_000, 'credits': ['known-credit']}
    atomic_write_json(path, state)
    atomic_write_json(path, state)
    path.write_text('{broken')
    loop = EffectLearningLoop(path, None)
    assert loop.state['xp'] == 1_000_000
    assert loop.state['credits'] == ['known-credit']


def test_experience_and_lesson_backup_recovery(tmp_path):
    engine = LearningEngine(tmp_path / 'experiences.json')
    engine.record('goal', 'action', 'result', .9)
    engine._save()
    engine.path.write_text('{broken')
    restored = LearningEngine(engine.path)
    assert len(restored.experiences) == 1
    assert restored.experiences[0]['result'] == 'result'


def test_legacy_episode_credit_is_not_awarded_again_after_upgrade(tmp_path):
    path=tmp_path/'effect.json'
    old={'goal':'same','action':'same','result':'same','strategy':'default','domain':'general','episode_id':'legacy','attempt':1}
    key=EffectLearningLoop._key(old)
    atomic_write_json(path,{'xp':1_000_000,'validated':1,'credits':[{'key':key,'xp':1_000_000}], 'evaluations':[{'key':key,**old}]})
    loop=EffectLearningLoop(path,LearningEngine(tmp_path/'learning.json'))
    result=loop.evaluate('same','same','same','same',{'verified':True,'score':.9},episode_id='new',attempt=2)
    assert not result['credit_awarded'] and loop.stats()['xp']==1_000_000
    assert loop.state['credits'][0]['key']==key
    restored=EffectLearningLoop(path,LearningEngine(tmp_path/'learning.json'))
    restored.evaluate('same','same','same','same',{'verified':True,'score':.9},episode_id='third')
    assert restored.stats()['xp']==1_000_000
