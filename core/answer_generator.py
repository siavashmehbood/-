import re
from .contracts import FinalAnswer


class AnswerGenerator:
    """Canonical boundary between cognitive state and human-facing output."""

    def __init__(self, engine, knowledge=None):
        self.engine = engine
        self.knowledge = knowledge

    def _knowledge_answer(self, text):
        if self.knowledge is None:
            return ''
        q = str(text).lower()
        queries = {
            'پایتخت ایران': ('ایران', 'پایتخت'),
            'پایتخت فرانسه': ('فرانسه', 'پایتخت'),
            'اسم پروژه': ('ایران', 'نام'),
            'نام پروژه': ('ایران', 'نام'),
        }
        for marker, (subject, predicate) in queries.items():
            if marker in q:
                fact = self.knowledge.resolve(subject, predicate) if hasattr(self.knowledge, 'resolve') else self.knowledge.best_fact(subject, predicate)
                if fact:
                    return str(fact.get('object', ''))
        return ''

    def mode(self, text, parsed=None):
        low = str(text).lower()
        if any(x in low for x in ('درست بود', 'اشتباه بود', 'غلط بود', 'عالی بود')):
            return 'FEEDBACK_ACK'
        if any(x in low for x in ('چرا', 'دلیل', 'علت')):
            return 'EXPLANATION'
        if any(x in low for x in ('چطور', 'چگونه', 'چه جوری', 'چجوری')):
            return 'PROCEDURE'
        if any(x in low for x in ('مقایسه', 'تفاوت', 'فرق', ' یا ')):
            return 'COMPARISON'
        if any(x in low for x in ('یادت', 'قبلاً', 'قبلا', 'موضوع قبلی', 'همون')):
            return 'MEMORY_RECALL'
        return 'DIRECT_FACT' if str(text).rstrip().endswith(('؟', '?')) else 'UNKNOWN'

    def generate(self, user_text, parsed_input, cognitive_context, history, frame):
        text = str(user_text).strip()
        rendered = self._knowledge_answer(text)
        if not rendered:
            rendered = self.engine.respond(text, parsed_input, cognitive_context or {}, history or [], frame or {})
        mode = self.mode(text, parsed_input)
        low = rendered.lower()
        unknown = 'unknown' in low or 'نمی‌دانم' in low or 'اطلاعات قابل اتکا' in low
        if unknown:
            mode = 'UNKNOWN'
        confidence = float((cognitive_context or {}).get('confidence', .5) or .5)
        evidence = []
        reasoning = (cognitive_context or {}).get('reasoning', {})
        if isinstance(reasoning, dict):
            reasoning = reasoning.get('reasoning', reasoning)
            evidence = list(reasoning.get('evidence', []) or [])
        return FinalAnswer(rendered, mode, confidence, evidence, '', unknown)
