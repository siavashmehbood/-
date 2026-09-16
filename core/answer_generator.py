from .contracts import FinalAnswer
from .cognitive_realizer import CognitiveRealizer


class AnswerGenerator:
    """Canonical boundary between cognitive state and human-facing output."""

    def __init__(self, engine, knowledge=None, runtime=None):
        self.engine = engine
        self.knowledge = knowledge
        self.runtime = runtime
        self.realizer = CognitiveRealizer()

    def _knowledge_answer(self, text):
        if self.knowledge is None:
            return ''
        q = str(text).lower()
        queries = {
            'پایتخت ایران': ('ایران', 'پایتخت'),
            'مرکز سیاسی کشور ایران': ('ایران', 'پایتخت'),
            'مرکز سیاسی ایران': ('ایران', 'پایتخت'),
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
        parsed = parsed_input if isinstance(parsed_input, dict) else getattr(parsed_input, '__dict__', {})
        cycle = dict(cognitive_context or {})
        if self.runtime is None:
            grounded = self._knowledge_answer(text)
            if grounded:
                return FinalAnswer(grounded, 'DIRECT_FACT', float(cycle.get('confidence', .9) or .9),
                                   [{'source': 'knowledge_graph', 'content': grounded, 'confidence': .9, 'kind': 'fact'}], '', False)
            # Compatibility for callers that use AnswerGenerator as a standalone
            # boundary; the live runtime always supplies the cognitive realizer.
            rendered = self.engine.respond(text, parsed, cycle, history or [], frame or {})
            return FinalAnswer(str(rendered), self.mode(text, parsed),
                               float(cycle.get('confidence', .5) or .5), [], '', 'unknown' in str(rendered).lower())
        result = self.realizer.realize(text, parsed, cycle, history or [], frame or {}, self.runtime)
        rendered = result.text.strip()
        mode = result.mode
        low = rendered.lower()
        unknown = mode == 'UNCERTAIN' or 'unknown' in low
        evidence = [item.__dict__ for item in result.evidence]
        return FinalAnswer(rendered, mode, result.confidence, evidence, '', unknown)
