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


@pytest.mark.parametrize('store', ['knowledge','procedures','skills','compositions','trusted_knowledge'])
def test_runtime_refuses_unrecoverable_learned_store_without_reset(tmp_path, store):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    path=tmp_path/'data'/f'{store}.json'
    path.parent.mkdir()
    path.write_text('{broken')
    path.with_suffix('.json.bak').write_text('{also broken')
    with pytest.raises(StateCorruptionError):
        IranRuntime(tmp_path)
    assert path.read_text()=='{broken'
    assert path.with_suffix('.json.bak').read_text()=='{also broken'


@pytest.mark.parametrize('store', ['knowledge','procedures','skills','compositions'])
def test_learned_store_recovers_backup_and_preserves_it_on_save(tmp_path, store):
    from knowledge.knowledge_graph import KnowledgeGraph
    from learning.procedural_memory import ProceduralMemory
    from learning.skill_system import SkillSystem
    factories={'knowledge':(KnowledgeGraph,'facts','_save'),
               'procedures':(ProceduralMemory,'procedures','_save'),
               'skills':(SkillSystem,'skills','_save'),
               'compositions':(lambda p: SkillSystem(p.with_name('skills.json')),'compositions','_save_compositions')}
    path=tmp_path/f'{store}.json'
    row={'subject':'fixture','predicate':'is','object':'retained','source':'fixture'}
    atomic_write_json(path,[row]);atomic_write_json(path,[row])
    path.write_text('{broken')
    factory,attribute,save=factories[store]
    obj=factory(path)
    assert getattr(obj,attribute)==[row]
    getattr(obj,save)()
    assert json.loads(path.read_text())==[row]
    assert json.loads(path.with_suffix('.json.bak').read_text())==[row]


@pytest.mark.parametrize('store', ['learning_goals','input_fabric','internet_learning','capability_learning'])
def test_learning_control_state_never_silently_resets(tmp_path, store):
    import shutil
    from pathlib import Path
    from runtime.app import IranRuntime
    shutil.copy(Path(__file__).parents[1]/'config.json',tmp_path)
    path=tmp_path/'data'/f'{store}.json';path.parent.mkdir()
    path.write_text('{broken')
    with pytest.raises(StateCorruptionError):
        IranRuntime(tmp_path)
    assert path.read_text()=='{broken'


def test_ingestion_backup_preserves_duplicate_detection(tmp_path):
    from learning.input_fabric import InputFabric
    fabric=InputFabric(tmp_path)
    event={'source':'document','input_type':'document','content':'existing knowledge'}
    fabric.events=[event];fabric._save();fabric._save()
    fabric.path.write_text('{broken')
    restored=InputFabric(tmp_path)
    assert restored.events==[event]
    assert restored._key('document','document','existing knowledge') in restored.seen


def test_goal_backup_recovers_even_when_primary_missing(tmp_path):
    from learning.self_directed import SelfDirectedLearning
    path=tmp_path/'goals.json'
    goals=SelfDirectedLearning(path)
    goal=goals.create_goal('ریاضی');goals._save();path.unlink()
    restored=SelfDirectedLearning(path)
    assert restored.goals[0].goal_id==goal['goal_id']


@pytest.mark.parametrize('broken', [[None], [{}], [{'proposal_id': 'x', 'kind': 'test', 'payload': {}, 'status': 'unknown'}], [{'proposal_id': 'x', 'kind': 'test', 'payload': {}, 'status': []}]])
def test_gate_structural_corruption_recovers_and_preserves_valid_backup(tmp_path, broken):
    path = tmp_path / 'gate.json'
    gate = LearningGate(path)
    row = gate.request('test', {'claim': 'retained'})
    gate.decide(row['proposal_id'], 'approved')
    atomic_write_json(path, json.loads(path.read_text()))
    path.write_text(json.dumps(broken))
    restored = LearningGate(path)
    assert restored.get(row['proposal_id'])['status'] == 'approved'
    restored.request('test', {'claim': 'new'})
    backup = json.loads(path.with_suffix('.json.bak').read_text())
    assert backup[0]['proposal_id'] == row['proposal_id']
    assert backup[0]['status'] == 'approved'


def test_gate_structural_corruption_without_backup_fails_closed(tmp_path):
    path = tmp_path / 'gate.json'
    path.write_text('[{}]')
    with pytest.raises(StateCorruptionError):
        LearningGate(path)
    assert path.read_text() == '[{}]'


def test_gate_checks_structure_on_every_reload(tmp_path):
    path = tmp_path / 'gate.json'
    gate = LearningGate(path)
    path.write_text('[{}]')
    with pytest.raises(StateCorruptionError):
        gate.request('test', {'claim': 'must not overwrite'})
    assert path.read_text() == '[{}]'
