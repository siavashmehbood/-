import shutil
from pathlib import Path
import pytest
from runtime.app import IranRuntime
from tests.chatgpt_test_helper import mark_chatgpt_correct


def runtime(root):
    shutil.copy(Path(__file__).parents[1] / 'config.json', root)
    return IranRuntime(root)


@pytest.mark.parametrize('failure_point', ['memory', 'decision', 'human_status'])
def test_interrupted_approval_rolls_back_and_can_be_retried(tmp_path, monkeypatch, failure_point):
    r = runtime(tmp_path)
    payload = {'subject': 'recovery fixture', 'predicate': 'color', 'value': 'blue', 'confidence': .8}
    proposal = r.learning_gate.request('memory.add_semantic_fact', payload)
    pid = proposal['proposal_id']
    mark_chatgpt_correct(r, pid, 'test fixture')
    if failure_point == 'memory':
        original = r.memory.add_semantic_fact
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('simulated interruption after SQLite commit')
        monkeypatch.setattr(r.memory, 'add_semantic_fact', fail)
    elif failure_point == 'decision':
        monkeypatch.setattr(r.learning_gate, 'decide', lambda *a: (_ for _ in ()).throw(RuntimeError('interrupted')))
    else:
        monkeypatch.setattr(r, '_set_human_review_status', lambda *a: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError):
        r.approve_learning(pid)
    with pytest.raises(RuntimeError, match='restart required'):
        r.handle('hello')
    r.close()
    restored = IranRuntime(tmp_path)
    assert restored.learning_gate.get(pid)['status'] == 'pending'
    assert restored.memory.conn.execute('select count(*) from semantic_facts where subject=?', ('recovery fixture',)).fetchone()[0] == 0
    assert restored.chatgpt_learning_review_status(pid)['reviewed']
    assert restored.approve_learning(pid)['ok']
    assert restored.learning_gate.get(pid)['status'] == 'approved'
    assert restored.memory.conn.execute('select count(*) from semantic_facts where subject=?', ('recovery fixture',)).fetchone()[0] == 1
    restored.close()


def test_recovery_keeps_unrelated_review_queue_rows(tmp_path, monkeypatch):
    from persistence import json_transaction
    r = runtime(tmp_path)
    p = r.learning_gate.request('knowledge.add_fact', {'subject': 'fixture', 'predicate': 'is', 'object': 'blue'})
    mark_chatgpt_correct(r, p['proposal_id'], 'fixture')
    def fail(*args):
        with json_transaction(r._chatgpt_review_path(), []) as rows:
            rows.append({'proposal_id': 'concurrent-candidate', 'status': 'pending'})
        raise RuntimeError('interrupted')
    monkeypatch.setattr(r.learning_gate, 'decide', fail)
    with pytest.raises(RuntimeError): r.approve_learning(p['proposal_id'])
    r.close()
    restored = IranRuntime(tmp_path)
    assert not restored.knowledge.query('fixture')
    import json
    assert any(x['proposal_id'] == 'concurrent-candidate' for x in json.loads(restored._chatgpt_review_path().read_text()))
    restored.close()


def test_process_exit_after_gate_commit_is_recovered(tmp_path):
    import subprocess
    import sys
    r = runtime(tmp_path)
    p = r.learning_gate.request('knowledge.add_fact', {'subject': 'crash fixture', 'predicate': 'is', 'object': 'blue'})
    mark_chatgpt_correct(r, p['proposal_id'], 'fixture')
    r.close()
    code = '''import os, sys
from runtime.app import IranRuntime
r = IranRuntime(sys.argv[1])
r._set_human_review_status = lambda *args: os._exit(23)
r.approve_learning(sys.argv[2])
'''
    child = subprocess.run([sys.executable, '-c', code, str(tmp_path), p['proposal_id']], cwd=Path(__file__).parents[1], timeout=20, capture_output=True)
    assert child.returncode == 23, child.stderr.decode()
    restored = IranRuntime(tmp_path)
    assert restored.learning_gate.get(p['proposal_id'])['status'] == 'pending'
    assert not restored.knowledge.query('crash fixture')
    assert restored.approve_learning(p['proposal_id'])['ok']
    assert restored.knowledge.query('crash fixture')
    restored.close()


def test_human_approval_does_not_approve_sibling_outcome(tmp_path):
    r = runtime(tmp_path)
    ids = []
    for action in ('first', 'second'):
        p = r.learning_gate.request('outcome.record', {'goal': 'fixture', 'action': action, 'result': 'observed', 'episode_id': 'shared', 'verified': True, 'score': .9})
        ids.append(p['proposal_id'])
        mark_chatgpt_correct(r, ids[-1], 'fixture')
    assert r.approve_learning(ids[0])['ok']
    assert r.learning_gate.get(ids[1])['status'] == 'pending'
    assert all(x['action'] != 'second' for x in r.outcome_learning.records)
    r.close()


def test_interrupted_correction_restores_unresolved_evidence(tmp_path, monkeypatch):
    r=runtime(tmp_path)
    p=r.knowledge.add_fact('ایران','پایتخت','شیراز',source='fixture')
    mark_chatgpt_correct(r,p['proposal_id'],'fixture only')
    assert r.approve_learning(p['proposal_id'])['ok']
    p=r.knowledge.contradict('ایران','پایتخت','تهران',source='correction_fixture')
    mark_chatgpt_correct(r,p['proposal_id'],'fixture only')
    monkeypatch.setattr(r.learning_gate,'decide',lambda *a: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError,match='interrupted'):
        r.approve_learning(p['proposal_id'])
    r.close()
    r=IranRuntime(tmp_path)
    assert r.learning_gate.get(p['proposal_id'])['status']=='pending'
    assert r.handle('پایتخت ایران کجاست؟').startswith('UNKNOWN:')
    assert r.approve_learning(p['proposal_id'])['ok']
    assert 'تهران' in r.handle('پایتخت ایران کجاست؟')
    r.close()
