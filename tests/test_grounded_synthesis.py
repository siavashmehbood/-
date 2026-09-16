from core.grounded_synthesizer import GroundedSynthesizer
from knowledge.knowledge_graph import KnowledgeGraph


class MemoryStub:
    def __init__(self, rows=None):
        self.rows = rows or []

    def working_context(self, query, limit=8):
        return self.rows[:limit]


class LearningStub:
    def recommended_strategy(self, goal, intent='general', domain='general'):
        return 'reuse-verified' if goal else 'evidence-first'


def test_answer_is_built_from_local_fact(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    graph.add_fact('ایران', 'پایتخت', 'تهران', .99, 'test')
    synth = GroundedSynthesizer(graph, MemoryStub(), LearningStub())

    result = synth.synthesize('پایتخت ایران چیست؟')

    assert result.status == 'GROUNDED'
    assert 'تهران' in result.answer
    assert result.sources == ['test']
    assert result.confidence > .8


def test_memory_can_ground_non_factual_turn(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    memory = MemoryStub([('user', 'من روی معماری شناختی کار می‌کنم')])
    synth = GroundedSynthesizer(graph, memory, LearningStub())

    memory_rows = synth._memory('معماری شناختی چیه؟')

    assert memory_rows
    assert 'معماری شناختی' in memory_rows[0][1]


def test_missing_evidence_stays_unknown(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    synth = GroundedSynthesizer(graph, MemoryStub(), LearningStub())

    result = synth.synthesize('پایتخت یک سیاره خیالی چیست؟')

    assert result.status == 'UNKNOWN'
    assert result.answer == ''
    assert result.confidence == 0.0


def test_strategy_is_retrieved_from_learning(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'knowledge.json')
    synth = GroundedSynthesizer(graph, MemoryStub(), LearningStub())

    result = synth.synthesize('موضوع پروژه چیست')

    assert result.strategy == 'reuse-verified'
