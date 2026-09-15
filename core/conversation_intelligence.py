from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class CognitiveContext:
    user_message: str
    question_type: str = 'statement'
    question_units: list[str] = field(default_factory=list)
    current_topic: str = ''
    active_goal: str = ''
    references: dict[str, str] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    relevant_memory: list[str] = field(default_factory=list)
    relevant_knowledge: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    predictions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    previous_answer: str = ''
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    confidence: float = 0.5
    answer_plan: list[str] = field(default_factory=list)


class QuestionAnalyzer:
    def analyze(self, text: str) -> tuple[str, list[str]]:
        t = self._clean(text)
        units = [u.strip() for u in re.split(r'\s+(?:و|همچنین)\s+', t) if u.strip()]
        if len(units) > 1: return 'multi_intent', units
        if 'چرا' in t: return 'why', units
        if any(x in t for x in ('چطور', 'چگونه', 'چه جوری')): return 'how', units
        if 'آیا' in t or t.endswith('?') or t.endswith('؟'): return 'question', units
        if any(x in t for x in ('مقایسه', 'فرق', 'تفاوت', 'بهتره')): return 'compare', units
        if any(x in t for x in ('ادامه بده', 'بیشتر بگو', 'توضیح بده', 'ساده‌تر', 'کوتاه‌تر', 'بهترش کن')): return 'follow_up', units
        return 'statement', units

    @staticmethod
    def _clean(text: str) -> str:
        return re.sub(r'\s+', ' ', str(text).strip().replace('ي', 'ی').replace('ك', 'ک'))


class ReferenceResolver:
    WORDS = ('این', 'همین', 'اون', 'آن', 'همون', 'همونو', 'قبلی', 'بالایی', 'این بخش', 'این جواب', 'این مشکل', 'روش قبلی', 'موضوع قبلی')

    def resolve(self, text: str, state) -> dict[str, str]:
        t = QuestionAnalyzer._clean(text)
        if not any(w in t for w in self.WORDS): return {}
        result = {}; candidate = state.referent or state.current_topic or state.last_user_message
        if candidate:
            for word in self.WORDS:
                if word in t: result[word] = candidate
        if 'موضوع قبلی' in t or 'برگردیم' in t:
            candidate = state.previous_topic() or candidate
            if candidate: result['موضوع قبلی'] = candidate
        return result


@dataclass
class AnswerVerification:
    status: str
    reasons: list[str] = field(default_factory=list)
    missing_units: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    score: float = 0.0


class AnswerPlanner:
    def build(self, context: CognitiveContext) -> list[str]:
        if context.question_type == 'multi_intent': return [f'answer: {u}' for u in context.question_units]
        if context.question_type in {'question', 'why', 'how', 'compare'}: return ['direct_answer', 'ground_with_local_evidence', 'state_uncertainty_if_needed']
        if context.question_type == 'follow_up': return ['resolve_reference', 'continue_previous_topic', 'answer_directly']
        return ['acknowledge_or_answer', 'preserve_context']


class AnswerVerifier:
    def verify(self, context: CognitiveContext, answer: str) -> AnswerVerification:
        answer = QuestionAnalyzer._clean(answer)
        if not answer: return AnswerVerification('REPAIR', ['empty_answer'], score=0.0)
        if context.references and not any(v[:20] in answer for v in context.references.values()):
            if context.question_type == 'follow_up': return AnswerVerification('REPAIR', ['wrong_reference'], score=0.25)
        missing = []
        if context.question_type == 'multi_intent':
            for unit in context.question_units:
                key = re.sub(r'[^آ-یA-Za-z0-9 ]', ' ', unit).strip()[:18]
                if key and not any(tok in answer for tok in key.split()[:2]): missing.append(unit)
        generic = any(x in answer for x in ('برای پاسخ به این پرسش', 'چند عامل قابل بررسی', 'اطلاعات بیشتری'))
        if missing: return AnswerVerification('REPAIR', ['incomplete_answer'], missing, score=0.35)
        if generic and len(context.user_message.split()) > 2: return AnswerVerification('REPAIR', ['too_generic'], score=0.4)
        return AnswerVerification('PASS', score=min(1.0, 0.65 + context.confidence * 0.35))


class AnswerRepair:
    def repair(self, context: CognitiveContext, answer: str, verification: AnswerVerification) -> str:
        if verification.status == 'PASS': return answer
        if 'wrong_reference' in verification.reasons:
            ref = next(iter(context.references.values()), context.current_topic)
            return f'منظورت را به «{ref}» وصل کردم. بر همان اساس: {answer}' if ref else 'مرجع جمله‌ات برایم روشن نیست؛ منظورت دقیقاً کدام بخش است؟'
        if 'incomplete_answer' in verification.reasons:
            return '\n'.join([answer] + [f'بخش «{u}» هم باید جداگانه بررسی شود.' for u in verification.missing_units])
        if 'too_generic' in verification.reasons: return f'پاسخ کوتاه: {answer}'
        return answer or 'برای پاسخ دقیق، یک نکته مشخص از موضوع را بگو.'


class ConversationIntelligence:
    """Deterministic local conversation layer placed before the legacy responder."""
    def __init__(self, state):
        self.state = state; self.analyzer = QuestionAnalyzer(); self.resolver = ReferenceResolver(); self.planner = AnswerPlanner(); self.verifier = AnswerVerifier(); self.repair = AnswerRepair()

    def build_context(self, text: str, history=None) -> CognitiveContext:
        qtype, units = self.analyzer.analyze(text); refs = self.resolver.resolve(text, self.state); history = history or []
        confidence = 0.9 if qtype != 'follow_up' or refs else 0.55
        context = CognitiveContext(user_message=text, question_type=qtype, question_units=units,
            current_topic=self.state.current_topic, active_goal=self.state.active_goal, references=refs,
            entities=list(self.state.entities), previous_answer=self.state.last_assistant_answer,
            conversation_history=history[-12:], confidence=confidence)
        context.answer_plan = self.planner.build(context)
        return context

    def enrich(self, context: CognitiveContext, memory=None):
        if memory is not None:
            try: context.relevant_memory = [str(c) for _, c, _ in memory.working_context(context.user_message, 8)]
            except Exception: pass
        context.answer_plan = self.planner.build(context); return context

    def validate_and_repair(self, context: CognitiveContext, answer: str) -> tuple[str, AnswerVerification]:
        verification = self.verifier.verify(context, answer)
        if verification.status != 'PASS':
            answer = self.repair.repair(context, answer, verification); verification = self.verifier.verify(context, answer)
        return answer, verification
