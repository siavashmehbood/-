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
        reference_markers = ('همون', 'قبلی', 'ادامه بده', 'این را', 'این رو', 'اون یکی', 'بیشتر توضیح بده')
        topic = (frame or {}).get('topic') or (frame or {}).get('goal')
        if any(marker in text for marker in reference_markers) and not topic and not history:
            return FinalAnswer('برای ادامه دادن، لطفاً موضوع یا پیام قبلی را مشخص کن؛ هنوز مرجع قابل اتکایی در حافظه ندارم.', 'CLARIFICATION', .25, [], 'موضوع مرجع را بپرس', False)
        ambiguity = getattr(parsed_input, 'ambiguity', None) if parsed_input is not None else None
        if ambiguity is not None and float(ambiguity) >= .75:
            alternatives = getattr(parsed_input, 'alternatives', []) or []
            labels = [str(item.get('goal', item)) for item in alternatives[:2]]
            suffix = ' یا '.join(labels)
            return FinalAnswer('منظورتان را دقیق مشخص نکردم' + (f': «{suffix}»؟' if suffix else '؛ لطفاً یک نمونه یا هدف دقیق‌تر بگویید.'), 'CLARIFICATION', round(1-float(ambiguity), 3), [], 'درخواست توضیح بیشتر', False)
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
