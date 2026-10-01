import json
import shutil
from pathlib import Path

from runtime.app import IranRuntime


def make_runtime(tmp_path):
    shutil.copy(Path(__file__).parents[1] / 'config.json', tmp_path / 'config.json')
    r = IranRuntime(tmp_path)
    r.internet_access.enable()
    return r


def test_candidate_reviewer_human_then_gate(tmp_path):
    r = make_runtime(tmp_path)
    try:
        candidate = r.queue_learning_candidate(
            'memory.add_semantic_fact',
            {'subject':'route fixture','predicate':'is','value':'blue','confidence':.9,'source':'fixture'},
            'route fixture candidate',
        )
        cid = candidate['proposal_id']
        assert cid.startswith('candidate_')
        assert r.learning_gate.stats()['total'] == 0

        r.chatgpt_review_worker.transport = lambda row: {
            'learn': True, 'reason': 'supported', 'confidence': .95,
            'corrections': [], 'provider': 'fixture', 'model': 'free:fixture',
        }
        reviewed = r.process_one_chatgpt_learning_review()
        assert reviewed['ok'] and reviewed['learn'] is True
        assert r.learning_gate.stats()['total'] == 0
        pending = r.human_learning_pending(10)
        assert [x['proposal_id'] for x in pending] == [cid]

        approved = r.approve_learning(cid, human_confirmed=True, source='test_human')
        assert approved['ok'], approved
        assert r.learning_gate.stats()['approved'] == 1
        review = r.chatgpt_learning_review_status(cid)['row']
        assert review['human_decision'] == 'approved'
        assert review['human_source'] == 'test_human'
        assert review.get('gate_proposal_id')
        facts = r.memory.semantic_search('route fixture', limit=10)
        assert facts
    finally:
        r.close()


def test_reviewer_reject_never_enters_gate_or_human_queue(tmp_path):
    r = make_runtime(tmp_path)
    try:
        candidate = r.queue_learning_candidate(
            'memory.add_semantic_fact',
            {'subject':'reject fixture','predicate':'is','value':'bad','confidence':.2,'source':'fixture'},
            'reject fixture candidate',
        )
        cid = candidate['proposal_id']
        r.chatgpt_review_worker.transport = lambda row: {
            'learn': False, 'reason': 'unsupported', 'confidence': .9,
            'corrections': [], 'provider': 'fixture', 'model': 'free:fixture',
        }
        reviewed = r.process_one_chatgpt_learning_review()
        assert reviewed['ok'] and reviewed['learn'] is False
        assert r.learning_gate.stats()['total'] == 0
        assert r.human_learning_pending(10) == []
        row = r.chatgpt_learning_review_status(cid)['row']
        assert row['status'] == 'rejected'
        assert row['chatgpt_decision'] == 'reject'
    finally:
        r.close()

