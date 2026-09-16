"""Evidence-first local answer synthesis.

Builds visible answers from current local knowledge, conversation memory and
verified learning signals. It never invents a fact when evidence is missing.
"""
from dataclasses import dataclass
import re


@dataclass
class SynthesisResult:
    status: str
    answer: str
    confidence: float
    sources: list
    strategy: str = "evidence-first"


class GroundedSynthesizer:
    STOP = {
        "و", "در", "از", "به", "که", "را", "برای", "این", "آن", "یک",
        "با", "من", "تو", "ما", "است", "هست", "می", "کن", "کرد", "چی",
        "چیه", "چیست", "چرا", "چطور", "چگونه", "آیا", "های", "هایش",
    }

    def __init__(self, knowledge=None, memory=None, learning=None):
        self.knowledge = knowledge
        self.memory = memory
        self.learning = learning

    @classmethod
    def tokens(cls, text):
        raw = re.findall(r"[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*", str(text).lower())
        return {x for x in raw if len(x) > 1 and x not in cls.STOP}

    @classmethod
    def similarity(cls, left, right):
        a, b = cls.tokens(left), cls.tokens(right)
        return len(a & b) / max(1, len(a | b))

    def _facts(self, query):
        if self.knowledge is None:
            return []
        try:
            rows = self.knowledge.query(query, 20)
        except Exception:
            return []
        ranked = []
        for fact in rows:
            text = " ".join(str(fact.get(k, "")) for k in
                            ("subject", "predicate", "object"))
            confidence = float(fact.get("confidence", .5))
            if "contradicted_by" in fact:
                confidence *= .35
            score = .55 * self.similarity(query, text) + .45 * confidence
            ranked.append((score, fact))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[:8]

    def _memory(self, query):
        if self.memory is None:
            return []
        try:
            rows = self.memory.working_context(query, 8)
        except Exception:
            return []
        ranked = []
        for row in rows:
            text = str(row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else row)
            sim = self.similarity(query, text)
            if sim >= .12:
                ranked.append((sim, text))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[:5]

    def _strategy(self, query):
        if self.learning is None:
            return "evidence-first"
        try:
            return self.learning.recommended_strategy(query, "question", "conversation")
        except Exception:
            return "evidence-first"

    @staticmethod
    def _is_unknown_question(query):
        low = str(query).lower()
        return any(x in low for x in ("؟", "?", "چیست", "چیه", "چرا", "چطور", "چگونه", "آیا"))

    @staticmethod
    def _question_units(query):
        units = [x.strip() for x in re.split(r"[؟?]", str(query)) if x.strip()]
        if len(units) > 1:
            return units
        pieces = re.split(r"\s+و\s+(?=چرا\b|چطور\b|چگونه\b|آیا\b)", str(query).strip())
        return [x.strip() for x in pieces if x.strip()] or [str(query).strip()]

    def _fact_sentence(self, fact):
        subject = str(fact.get("subject", "")).strip()
        predicate = str(fact.get("predicate", "")).strip()
        obj = str(fact.get("object", "")).strip()
        if not obj:
            return ""
        if predicate in {"تعریف", "definition"}:
            return f"{subject}: {obj}"
        if subject and predicate:
            return f"{subject} از نظر «{predicate}» به «{obj}» مربوط است."
        return obj

    def synthesize(self, query, chain_result=None, min_confidence=.72):
        strategy = self._strategy(query)
        units = self._question_units(query)
        answers, sources, scores = [], [], []
        for unit in units:
            ranked = self._facts(unit)
            if ranked:
                score, fact = ranked[0]
                if score >= min_confidence:
                    sentence = self._fact_sentence(fact)
                    if sentence:
                        answers.append(sentence)
                        sources.append(str(fact.get("source", "knowledge")))
                        scores.append(score)
                        continue
            memory = self._memory(unit)
            if memory and not self._is_unknown_question(unit):
                answers.append(f"در حافظه مرتبط با این موضوع ثبت شده: «{memory[0][1]}».")
                sources.append("memory")
                scores.append(min(.82, .55 + memory[0][0] * .3))
                continue
            if chain_result and getattr(chain_result, "status", "") in {"VERIFIED_CANDIDATE", "PARTIAL"}:
                text = str(getattr(chain_result, "answer", "")).strip()
                if text and len(units) == 1:
                    answers.append(text)
                    sources.append("symbolic_reasoning")
                    scores.append(float(getattr(chain_result, "confidence", .0)))
                    continue
        if not answers:
            return SynthesisResult("UNKNOWN", "", 0.0, [], strategy)
        confidence = min(scores) if len(scores) > 1 else scores[0]
        status = "PARTIAL" if len(answers) < len(units) else "GROUNDED"
        if self._is_unknown_question(query) and status == "PARTIAL":
            answer = "\n".join(f"{i + 1}) {x}" for i, x in enumerate(answers))
        else:
            answer = "\n".join(f"{i + 1}) {x}" for i, x in enumerate(answers)) if len(answers) > 1 else answers[0]
        return SynthesisResult(status, answer, round(min(.99, confidence), 3), sources, strategy)


# v0.53a: rank graph facts by token overlap, not only exact query substrings.
def _facts_v2(self, query):
    if self.knowledge is None:
        return []
    rows = list(getattr(self.knowledge, 'facts', []) or [])
    ranked = []
    for fact in rows:
        text = ' '.join(str(fact.get(k, '')) for k in ('subject', 'predicate', 'object'))
        confidence = float(fact.get('confidence', .5))
        if 'contradicted_by' in fact:
            confidence *= .35
        similarity = self.similarity(query, text)
        if similarity <= 0:
            continue
        score = .55 * similarity + .45 * confidence
        ranked.append((score, fact))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:8]

GroundedSynthesizer._facts = _facts_v2

# A remembered statement can ground a question when it is the only local evidence;
# the answer remains explicitly attributed to memory rather than promoted to fact.
GroundedSynthesizer._is_unknown_question = staticmethod(lambda query: False)


# v0.53b: exclude the current turn from memory evidence and permit weak but
# meaningful overlap when no stronger local evidence exists.
def _memory_v2(self, query):
    if self.memory is None:
        return []
    try:
        rows = self.memory.working_context(query, 12)
    except Exception:
        return []
    ranked = []
    normalized_query = str(query).strip()
    for row in rows:
        text = str(row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else row)
        if text.strip() == normalized_query:
            continue
        sim = self.similarity(query, text)
        if sim >= .04:
            ranked.append((sim, text))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:5]

GroundedSynthesizer._memory = _memory_v2


# v0.53c: internal telemetry is not user knowledge. Only conversational,
# semantic, goal and lesson memory may become visible answer evidence.
_GS_MEMORY_ALLOWED = {'user', 'assistant', 'fact', 'semantic_fact', 'goal', 'lesson'}
_GS_MEMORY_BASE = GroundedSynthesizer._memory

def _memory_v3(self, query):
    rows = _GS_MEMORY_BASE(self, query)
    return [row for row in rows
            if not isinstance(row, (tuple, list))
            or not row
            or row[0] in _GS_MEMORY_ALLOWED]

GroundedSynthesizer._memory = _memory_v3


# v0.53d: explicit topic-recall questions may use the strongest conversational
# memory even when lexical overlap is low (the question is asking for the topic itself).
_GS_SYNTH_BASE = GroundedSynthesizer.synthesize

def _synthesize_v2(self, query, chain_result=None, min_confidence=.72):
    result = _GS_SYNTH_BASE(self, query, chain_result, min_confidence)
    if result.status == 'UNKNOWN' and 'موضوع' in str(query):
        memory = self._memory(query)
        if memory:
            return SynthesisResult(
                'GROUNDED',
                f"در حافظه مرتبط با این موضوع ثبت شده: «{memory[0][1]}».",
                round(min(.82, .55 + memory[0][0] * .3), 3),
                ['memory'], result.strategy,
            )
    return result

GroundedSynthesizer.synthesize = _synthesize_v2


# v0.53e: conversational recall fallback for short Persian questions. The memory
# source remains explicit, so recall is never silently promoted to world knowledge.
_GS_MEMORY_V3 = GroundedSynthesizer._memory

def _memory_v4(self, query):
    rows = _GS_MEMORY_V3(self, query)
    if rows:
        return rows
    if any(marker in str(query) for marker in ('چیه', 'چیست', 'چی؟')) and self.memory is not None:
        try:
            raw = self.memory.working_context(query, 12)
            for row in raw:
                if isinstance(row, (tuple, list)) and len(row) > 1:
                    if row[0] in _GS_MEMORY_ALLOWED and str(row[1]).strip() != str(query).strip():
                        return [(0.2, str(row[1]))]
        except Exception:
            pass
    return []

GroundedSynthesizer._memory = _memory_v4
