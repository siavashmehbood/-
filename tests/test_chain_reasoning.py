import json
from pathlib import Path

from core.chain_reasoner import ChainReasoner
from knowledge.knowledge_graph import KnowledgeGraph


class MemoryStub:
    def working_context(self, query, limit=6):
        return []


def test_multi_hop_reasoning_propagates_confidence(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    graph.add_fact('ایران', 'پایتخت', 'تهران', .99, 'test')
    graph.add_fact('تهران', 'کشور', 'ایران', .98, 'test')
    reasoner = ChainReasoner(graph, MemoryStub(), tmp_path / 'episodes.json')

    result = reasoner.reason('پایتخت ایران چیست؟')

    assert result.status in {'VERIFIED_CANDIDATE', 'PARTIAL'}
    assert 'تهران' in result.answer
    assert result.confidence > .7
    assert any(step['kind'] == 'retrieve' for step in result.steps)


def test_unknown_never_becomes_a_guess(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    reasoner = ChainReasoner(graph, MemoryStub(), tmp_path / 'episodes.json')

    result = reasoner.reason('نام یک واقعیت ساختگی چیست؟')

    assert result.status == 'UNKNOWN'
    assert result.answer == ''
    assert result.assumptions


def test_reasoning_experience_changes_depth_strategy(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    reasoner = ChainReasoner(graph, MemoryStub(), tmp_path / 'episodes.json')
    result = reasoner.reason('پایتخت ایران چیست؟')
    reasoner.record('پایتخت ایران چیست؟', result, accepted=True, score=.95)
    strategy = reasoner.strategy('پایتخت ایران چیست؟')

    assert strategy['samples'] == 1
    assert strategy['depth'] in {2, 3}


def test_episode_persistence(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    graph.add_fact('فرانسه', 'پایتخت', 'پاریس', .99, 'test')
    path = tmp_path / 'episodes.json'
    reasoner = ChainReasoner(graph, MemoryStub(), path)
    result = reasoner.reason('پایتخت فرانسه چیست؟')
    reasoner.record('پایتخت فرانسه چیست؟', result, accepted=True, score=.9)

    data = json.loads(path.read_text(encoding='utf-8'))
    assert len(data) == 1
    assert data[0]['accepted'] is True
