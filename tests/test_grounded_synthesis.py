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


def test_relevant_memory_survives_role_filter_without_question_fallback():
    synth=GroundedSynthesizer(memory=MemoryStub([('user','پروژه دانا فروشگاه کتاب است')]))
    rows=synth._memory('درباره پروژه دانا توضیح بده')
    assert rows and 'فروشگاه کتاب' in rows[0][1]


def test_unrelated_recent_memory_cannot_ground_unknown_question():
    synth=GroundedSynthesizer(memory=MemoryStub([('user','من امروز به بازار رفتم')]))
    assert synth.synthesize('جرم سیاره نپتون چیست؟').status=='UNKNOWN'


def test_assistant_output_is_not_its_own_factual_evidence():
    synth=GroundedSynthesizer(memory=MemoryStub([('assistant','ماه از پنیر ساخته شده است')]))
    assert synth.synthesize('جنس ماه چیست؟').status=='UNKNOWN'


def test_telemetry_and_user_questions_are_not_knowledge():
    synth=GroundedSynthesizer(memory=MemoryStub([
        ('cognitive_state','پروژه دانا فعال است'),
        ('user','پروژه دانا چیست؟'),
        ('user','پروژه دانا فروشگاه کتاب است'),
    ]))
    rows=synth._memory('درباره پروژه دانا توضیح بده')
    assert len(rows)==1 and 'فروشگاه کتاب' in rows[0][1]
