"""Deterministic Persian reference intelligence.
No model, network, embedding or external data is used.
"""
from dataclasses import dataclass, asdict
import re


@dataclass
class ReferenceCandidate:
    value: str
    source: str
    evidence: str
    score: float
    recency: int = 0
    topic_match: float = 0.0


@dataclass
class ReferenceResolution:
    candidate: str = ""
    confidence: float = 0.0
    ambiguous: bool = False
    candidates: list = None
    trigger: str = ""

    def to_dict(self):
        return asdict(self)


class ReferenceIntelligence:
    """Ranks explicit, current, previous and hierarchical context deterministically."""

    DEMONSTRATIVES = ("این", "این بخش", "این جواب", "این مشکل", "همین")
    PREVIOUS = ("همون قبلی", "اون قبلی", "موضوع قبلی", "بحث قبلی", "بخش قبلی", "قبلیش", "قبلی")
    DISTAL = ("آن", "اون", "آن بخش", "ساختار آن", "ساختارش", "حافظه‌اش", "حافظه اش")
    FOLLOWUPS = ("چرا", "چطور", "چگونه", "ادامه بده", "بیشتر بگو", "توضیح بده", "مثال بزن")

    def resolve(self, text, state, history=None, tracker=None):
        t = self._clean(text)
        history = history or []
        trigger = self._trigger(t)
        candidates = self._candidates(t, state, history, tracker)
        if not candidates:
            return ReferenceResolution(trigger=trigger, candidates=[])
        ranked = sorted(candidates, key=lambda c: (c.score, c.topic_match, -c.recency), reverse=True)
        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        gap = top.score - second.score if second else 1.0
        ambiguous = bool(second and gap < 0.16 and top.score < 0.9)
        confidence = max(0.0, min(0.99, top.score if not ambiguous else top.score * 0.72))
        return ReferenceResolution(
            candidate="" if ambiguous else top.value,
            confidence=round(confidence, 3),
            ambiguous=ambiguous,
            candidates=[asdict(x) for x in ranked[:5]],
            trigger=trigger,
        )

    def _candidates(self, text, state, history, tracker):
        rows = []
        seen = set()
        def add(value, source, evidence, score, recency=0, topic_match=0.0):
            value = self._clean(value)
            if len(value) < 2 or value in seen:
                return
            seen.add(value)
            rows.append(ReferenceCandidate(value, source, evidence, score, recency, topic_match))

        current = self._clean(getattr(state, "current_topic", ""))
        previous = self._previous(state)
        latest = self._clean(getattr(state, "references", {}).get("latest", ""))
        active_goal = self._clean(getattr(state, "active_goal", ""))
        if current:
            add(current, "current_topic", "active topic", 0.90, 0, 0.35)
        if latest:
            add(latest, "latest_reference", "stored reference", 0.86, 1, 0.30)
        if previous:
            add(previous, "previous_topic", "topic stack", 0.84, 2, 0.45)
        if active_goal:
            add(active_goal, "active_goal", "active goal", 0.62, 3, 0.20)
        if tracker:
            snap = tracker.snapshot()
            for row in snap.topics[:8]:
                add(row.get("value", ""), "context_tracker", "ranked topic", 0.48 + min(.30, float(row.get("score", 0)) * .04), int(row.get("age", 0)), .25 if row.get("parent") else .0)
        for i, item in enumerate(reversed(history[-8:])):
            content = self._content(item)
            if self._is_reference_candidate(content):
                add(content, "history", "recent conversation", max(.32, .62 - i * .05), i + 1, .05)
        return self._boost_by_trigger(rows, text, current, previous)
    def _boost_by_trigger(self, rows, text, current, previous):
        if any(x in text for x in self.PREVIOUS):
            for row in rows:
                if row.value == previous:
                    row.score += .22
                elif row.value == current:
                    row.score -= .18
        elif any(x in text for x in self.DEMONSTRATIVES) or any(x in text for x in self.DISTAL):
            for row in rows:
                if row.value == current:
                    row.score += .12
        if any(x in text for x in self.FOLLOWUPS):
            for row in rows:
                if row.value == current:
                    row.score += .10
        return rows

    @staticmethod
    def _previous(state):
        stack = list(getattr(state, "topic_stack", []) or [])
        current = str(getattr(state, "current_topic", "") or "")
        if stack:
            return str(stack[-1])
        return ""

    @staticmethod
    def _content(item):
        if isinstance(item, (tuple, list)) and len(item) > 1:
            return str(item[1])
        if isinstance(item, dict):
            return str(item.get("content", item.get("text", "")))
        return str(item)

    @classmethod
    def _is_reference_candidate(cls, value):
        value = cls._clean(value)
        if not value or value in cls.FOLLOWUPS:
            return False
        return len(re.sub(r"[^آ-یA-Za-z0-9]", "", value)) >= 2

    @classmethod
    def _trigger(cls, text):
        for group in (cls.PREVIOUS, cls.DEMONSTRATIVES, cls.DISTAL, cls.FOLLOWUPS):
            for marker in group:
                if marker in text:
                    return marker
        return ""

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", str(value or "").strip().replace("ي", "ی").replace("ك", "ک")).rstrip("؟?!.").strip()


# v2.1 compatibility/precision layer: explicit ordinal and lexical references win.
_reference_resolve_v21 = ReferenceIntelligence.resolve

def _resolve_v21(self, text, state, history=None, tracker=None):
    t = self._clean(text)
    stack = list(getattr(state, "topic_stack", []) or [])
    if "بحث اول" in t or "مورد اول" in t or t == "اولی":
        return ReferenceResolution(stack[0] if stack else "", .98, False, [], "اولی")
    if "بحث دوم" in t or "مورد دوم" in t or t == "دومی":
        return ReferenceResolution(stack[1] if len(stack) > 1 else "", .98, False, [], "دومی")
    known = stack + [getattr(state, "current_topic", ""), getattr(state, "references", {}).get("latest", "")]
    for value in reversed([self._clean(x) for x in known]):
        if value and value in t and value != t:
            return ReferenceResolution(value, .99, False, [], value)
    return _reference_resolve_v21(self, text, state, history, tracker)

ReferenceIntelligence.resolve = _resolve_v21
