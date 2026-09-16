"""Symbolic language realization for IRAN.

Clean-room ideas: PRISM semantic weaving, LIDA global-workspace output selection,
NARS evidence/status, Soar goal state, AtomSpace provenance, and humind-style
working/episodic/semantic separation. No model, API, or response cache.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RealizationEvidence:
    text: str
    source: str = "unknown"
    confidence: float = 0.0
    kind: str = "evidence"


@dataclass
class Realization:
    text: str
    mode: str
    confidence: float
    evidence: list[RealizationEvidence] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)


class CognitiveRealizer:
    """Turn structured cognitive state into newly composed Persian language."""

    _REF_WORDS = {"همون", "همونو", "قبلی", "ادامه", "این", "اون", "همین"}

    def clean(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().replace("ي", "ی").replace("ك", "ک"))

    def _evidence(self, cycle: dict) -> list[RealizationEvidence]:
        rows: list[RealizationEvidence] = []
        for item in cycle.get("evidence", []) or []:
            if isinstance(item, dict):
                text = self.clean(item.get("content", ""))
                if text:
                    rows.append(RealizationEvidence(text, str(item.get("source", "unknown")),
                                                    float(item.get("confidence", .5)),
                                                    str(item.get("kind", "evidence"))))
        return rows

    def _observations(self, cycle: dict) -> list[dict]:
        return [x for x in (cycle.get("current_observations", []) or []) if isinstance(x, dict)]

    def _nars(self, runtime, text: str):
        nars = getattr(runtime, "nars", None)
        if nars is None:
            return None
        try:
            answer = nars.answer_text(text)
            if answer and answer.answer:
                return answer
        except Exception:
            pass
        return None

    def _graph_answer(self, runtime, text: str):
        graph = getattr(runtime, "knowledge", None)
        if graph is None:
            return None
        try:
            rows = graph.query(text, 20)
        except Exception:
            return None
        if not rows:
            return None
        # Only knowledge facts may become a factual answer. Experience/procedure
        # records are evidence for learning, not world facts.
        valid = []
        query_words = set(re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*', self.clean(text).lower()))
        for row in rows:
            if not isinstance(row, dict) or not row.get("subject") or not row.get("predicate"):
                continue
            if not row.get("object"):
                continue
            subject_words = set(re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*', self.clean(row.get("subject")).lower()))
            if subject_words and not (query_words & subject_words):
                continue
            row_words = set(re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*',
                                       self.clean(f'{row.get("subject")} {row.get("predicate")} {row.get("object")}').lower()))
            overlap = len(query_words & row_words)
            valid.append((overlap, float(row.get("confidence", .0)), row))
        if not valid:
            return None
        _, confidence, best = max(valid, key=lambda x: (x[0], x[1]))
        value = self.clean(best.get("object", best.get("value", "")))
        return (value, confidence, best) if value else None

    def _fact_sentence(self, fact: dict) -> str:
        predicate = self.clean(fact.get("predicate", ""))
        value = self.clean(fact.get("object", ""))
        if not value:
            return ""
        forms = {
            "name": f'ثبت کردم که نامت «{value}» است.',
            "likes": f'ثبت کردم که «{value}» را دوست داری.',
            "dislikes": f'ثبت کردم که «{value}» را دوست نداری.',
            "role": f'ثبت کردم که نقش تو «{value}» است.',
            "goal": f'ثبت کردم که هدفت «{value}» است.',
        }
        return forms.get(predicate, f'این واقعیت را ثبت کردم: «{predicate} = {value}».')

    def _nars_sentence(self, answer: Any, text: str) -> str:
        raw = self.clean(getattr(answer, "answer", ""))
        evidence = getattr(answer, "evidence", []) or []
        if raw.startswith("بله؛") or raw.startswith("خیر؛"):
            return raw
        if evidence and isinstance(evidence[0], dict):
            row = evidence[0]
            subject = self.clean(row.get("subject"))
            predicate = self.clean(row.get("predicate")).replace("_", " ")
            value = self.clean(row.get("value"))
            if subject and predicate and value:
                if predicate == "پایتخت":
                    return f'پایتخت {subject} «{value}» است.'
                if predicate == "دمای جوش":
                    return f'دمای جوش {subject} در فشار استاندارد «{value}» است.'
                if predicate == "در" and self.clean(text).endswith(("چیست", "چیه")):
                    return f'«{value}».'
                return f'{predicate} {subject} «{value}» است.'
        return f'بر اساس استدلال محلی، «{raw}» است.' if raw else ""

    def _question_from_memory(self, text: str, cycle: dict, evidence: list[RealizationEvidence]):
        q = self.clean(text).rstrip("؟?")
        low = q.lower()
        if any(x in low for x in ("اسم", "نام")):
            facts = [x for x in cycle.get("user_model", {}).get("facts", []) if x.get("predicate") == "name"]
            if facts:
                value = self.clean(facts[-1].get("object"))
                return f'بر اساس واقعیتی که خودت ثبت کردی، نامت «{value}» است.'
        if any(x in low for x in ("دوست دارم", "دوست داشتم", "علایق", "علاقه")):
            facts = [x for x in cycle.get("user_model", {}).get("facts", []) if x.get("predicate") == "likes"]
            if facts:
                values = []
                for fact in facts:
                    value = self.clean(fact.get("object"))
                    if value and value not in values:
                        values.append(value)
                return "بر اساس ترجیحات ثبت‌شده، گفتی «" + "»، «".join(values) + "» را دوست داری."
        return ""

    def _reference(self, text: str, frame: dict, evidence: list[RealizationEvidence]) -> str:
        words = set(self.clean(text).lower().split())
        if not words & self._REF_WORDS:
            return ""
        topic = self.clean(frame.get("topic") or frame.get("goal"))
        if topic and not (set(topic.lower().split()) & self._REF_WORDS):
            return topic
        for item in reversed(evidence):
            if item.text and not (set(item.text.lower().split()) & self._REF_WORDS):
                return item.text
        return ""

    def _why(self, cycle: dict, evidence: list[RealizationEvidence]) -> Realization:
        reasoning = cycle.get("reasoning", {}) or {}
        if isinstance(reasoning, dict):
            reasoning = reasoning.get("reasoning", reasoning)
        hypotheses = [self.clean(x) for x in reasoning.get("hypotheses", []) if self.clean(x)]
        lines = []
        if hypotheses:
            lines.append("برای این علت، چند فرضیه در هسته ساخته شده: " + "، ".join(hypotheses[:4]) + ".")
        if evidence:
            strongest = sorted(evidence, key=lambda x: x.confidence, reverse=True)[:2]
            lines.append("قوی‌ترین شواهد فعلی: " + "؛ ".join(f'«{x.text}»' for x in strongest) + ".")
        if not lines:
            lines.append("برای علت قطعی، هنوز شاهد کافی ندارم؛ بنابراین یک علت را به‌عنوان حقیقت قطعی اعلام نمی‌کنم.")
        confidence = float(cycle.get("confidence", .4) or .4)
        return Realization(" ".join(lines), "EXPLANATION", confidence, evidence[:3])

    def _how(self, cycle: dict) -> Realization:
        reasoning = cycle.get("reasoning", {}) or {}
        if isinstance(reasoning, dict):
            reasoning = reasoning.get("reasoning", reasoning)
        actions = [self.clean(x) for x in reasoning.get("next_actions", []) if self.clean(x)]
        plan = [self.clean(x) for x in cycle.get("plan", []) if self.clean(x)]
        steps = actions[:6] or plan[:6]
        if not steps:
            steps = ["فهم هدف", "بررسی زمینه و شواهد", "ساخت گزینه‌ها", "انتخاب اقدام", "آزمون نتیجه"]
        return Realization("برای این کار، مسیر فعلی هسته این است: " + " → ".join(steps) + ".",
                           "PROCEDURE", float(cycle.get("confidence", .5) or .5))

    def _compare(self, text: str, cycle: dict, evidence: list[RealizationEvidence]) -> Realization:
        parts = re.split(r"\s+(?:یا|و)\s+", self.clean(text).rstrip("؟?"), maxsplit=1)
        if len(parts) != 2:
            return Realization("دو گزینه مستقل از متن استخراج نشد؛ مقایسه را قطعی نمی‌کنم.", "COMPARISON", .35)
        a, b = (self.clean(x) for x in parts)
        criteria = ["هدف", "شواهد", "هزینه", "ریسک", "برگشت‌پذیری"]
        return Realization(
            f'برای مقایسه «{a}» و «{b}»، معیارهای مرتبط را {"، ".join(criteria)} در نظر می‌گیرم. '
            "با شواهد فعلی نتیجه را مشروط نگه می‌دارم و برنده ساختگی اعلام نمی‌کنم.",
            "COMPARISON", float(cycle.get("confidence", .5) or .5), evidence[:3])

    def _general(self, text: str, cycle: dict, evidence: list[RealizationEvidence], runtime, frame: dict) -> Realization:
        reference = self._reference(text, frame, evidence)
        if reference:
            return Realization(f'این پیام را به زمینه «{self.clean(reference)[:220]}» مرتبط کردم و همان را مرجع تحلیل قرار دادم.',
                               "REFERENCE", float(cycle.get("confidence", .45) or .45), evidence[:2])
        nars = self._nars(runtime, text)
        if nars and float(nars.confidence) >= .70:
            ev = [RealizationEvidence(str(x), "nars", float(nars.confidence), "reasoning") for x in nars.evidence[:3]]
            return Realization(f'بر اساس استدلال محلی، پاسخ «{self.clean(nars.answer)}» است.',
                               "NARS_REASONING", float(nars.confidence), ev)
        graph = self._graph_answer(runtime, text)
        if graph and graph[1] >= .70:
            value, confidence, fact = graph
            ev = [RealizationEvidence(str(fact), "knowledge_graph", confidence, "fact")]
            return Realization(f'در دانش محلی، نتیجه مرتبط «{value}» است.', "KNOWLEDGE", confidence, ev)
        observations = self._observations(cycle)
        if observations:
            rendered = [self._fact_sentence(x) for x in observations]
            rendered = [x for x in rendered if x]
            if rendered:
                return Realization(" ".join(rendered), "LEARNING", float(cycle.get("confidence", .6) or .6))
        if cycle.get("unresolved"):
            issues = "، ".join(self.clean(x) for x in cycle["unresolved"][:3])
            return Realization(f'هنوز برای این موضوع شواهد کافی ندارم؛ مسئله‌های باز: {issues}.',
                               "UNCERTAIN", min(.5, float(cycle.get("confidence", .4) or .4)), evidence[:2], cycle["unresolved"][:3])
        return Realization("موضوع را در زمینه فعلی تحلیل کردم، اما برای ساخت یک نتیجه قابل اتکا شاهد مستقلی پیدا نکردم.",
                           "UNCERTAIN", .30, evidence[:2], ["insufficient_evidence"])

    def realize(self, text: str, parsed: Any, cycle: dict, history: list, frame: dict, runtime) -> Realization:
        """Select one cognitive result from the global workspace and realize it."""
        cycle = dict(cycle or {})
        evidence = self._evidence(cycle)
        observations = self._observations(cycle)
        low = self.clean(text).lower()
        intent = parsed.get("intent", "general") if isinstance(parsed, dict) else getattr(parsed, "intent", "general")
        question_type = parsed.get("question_type", "") if isinstance(parsed, dict) else getattr(parsed, "question_type", "")

        # User memory is evidence owned by the dialogue participant. It is checked
        # before generic world-knowledge retrieval so procedural records cannot
        # masquerade as personal facts.
        personal = self._question_from_memory(text, cycle, evidence)
        if personal:
            return Realization(personal, "MEMORY", float(cycle.get("confidence", .7) or .7))

        # Social input is still processed by the same workspace; the wording is
        # composed from the detected communicative intent rather than a saved reply.
        if intent in {"greeting", "salutation"} or low in {"سلام", "درود", "hello", "hi"}:
            return Realization("سلام. من ایران هستم؛ گفت‌وگو را از همین ورودی شروع می‌کنم. موضوعت را بگو تا آن را تحلیل و دنبال کنیم.",
                               "GREETING", max(.5, float(cycle.get("confidence", .5) or .5)))

        # Declarative input is knowledge acquisition, not a response lookup.
        if observations and not question_type and intent not in {"question", "compare", "memory"}:
            rendered = [self._fact_sentence(x) for x in observations]
            rendered = [x for x in rendered if x]
            if rendered:
                return Realization(" ".join(rendered), "OBSERVATION", float(cycle.get("confidence", .7) or .7))

        if question_type == "why" or "چرا" in low:
            if low.rstrip("؟?") == "چرا" and history:
                previous = ""
                for item in reversed(history):
                    if isinstance(item, (tuple, list)) and len(item) >= 2 and item[0] == "user":
                        previous = self.clean(item[1]); break
                    if isinstance(item, str) and item.strip():
                        previous = self.clean(item); break
                prior_nars = self._nars(runtime, previous) if previous else None
                if prior_nars and prior_nars.answer:
                    return Realization(f'اگر منظورت سؤال قبلی است، دلیل مرتبط با آن از همین شاهد به دست می‌آید: {self._nars_sentence(prior_nars, previous)}',
                                       "FOLLOWUP_EXPLANATION", float(prior_nars.confidence),
                                       [RealizationEvidence(str(x), "nars", float(prior_nars.confidence), "reasoning") for x in prior_nars.evidence[:2]])
            return self._why(cycle, evidence)
        if question_type in {"yes_no", "open"} and intent == "question":
            memory_answer = self._question_from_memory(text, cycle, evidence)
            if memory_answer:
                return Realization(memory_answer, "MEMORY", float(cycle.get("confidence", .7) or .7))
        if question_type == "how" or any(x in low for x in ("چطور", "چگونه", "چه جوری", "چجوری")):
            return self._how(cycle)
        if intent == "compare" or any(x in low for x in ("مقایسه", "تفاوت", "فرق")):
            return self._compare(text, cycle, evidence)
        if intent == "memory" or any(x in low for x in ("یادت", "قبلاً", "قبلا", "همون", "قبلی", "ادامه بده")):
            remembered = self._question_from_memory(text, cycle, evidence)
            if remembered:
                return Realization(remembered, "MEMORY", float(cycle.get("confidence", .65) or .65))
            reference = self._reference(text, frame, evidence)
            if reference:
                return Realization(f'مرجع قبلی را «{self.clean(reference)[:220]}» تشخیص دادم. حالا می‌توانیم همان را ادامه دهیم.',
                                   "REFERENCE", .65, evidence[:2])
        # Explicit local reasoning gets priority over generic language composition.
        if question_type or intent == "question":
            nars = self._nars(runtime, text)
            if nars and float(nars.confidence) >= .55:
                ev = [RealizationEvidence(str(x), "nars", float(nars.confidence), "reasoning") for x in nars.evidence[:4]]
                status = "با تعارض" if nars.status == "conflict" else "با شواهد محلی"
                sentence = self._nars_sentence(nars, text)
                mode = "DIRECT_FACT" if nars.status == "derived" and not str(nars.answer).startswith(("بله؛", "خیر؛")) else "REASONING"
                return Realization(sentence, mode, float(nars.confidence), ev)
            graph = self._graph_answer(runtime, text)
            if graph:
                value, confidence, fact = graph
                ev = [RealizationEvidence(str(fact), "knowledge_graph", confidence, "fact")]
                return Realization(f'بر اساس دانش محلی، «{value}» است.', "KNOWLEDGE", confidence, ev)
        return self._general(text, cycle, evidence, runtime, frame)
