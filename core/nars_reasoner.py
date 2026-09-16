"""NARS-inspired symbolic reasoner for IRAN.

Clean-room Python implementation of the architectural ideas used by NARS/ONA:
judgments, questions, goals, evidence-weighted beliefs, revision and derivation.
It is deliberately model-free and dependency-free.
"""
from dataclasses import dataclass, field
import re
from time import time


@dataclass
class Belief:
    subject: str
    predicate: str
    value: str
    frequency: float = 1.0
    confidence: float = 0.5
    source: str = "internal"
    updated_at: float = field(default_factory=time)

    @property
    def strength(self):
        return self.frequency * self.confidence


@dataclass
class Task:
    kind: str
    subject: str = ""
    predicate: str = ""
    value: str = ""
    priority: float = 0.5
    source: str = "input"


@dataclass
class ReasoningAnswer:
    answer: str
    confidence: float
    evidence: list = field(default_factory=list)
    derivation: list = field(default_factory=list)
    status: str = "unknown"


class NarsInspiredReasoner:
    """Small local reasoning store with revision and syllogistic derivation."""

    def __init__(self, capacity=4096):
        self.capacity = int(capacity)
        self.beliefs = []
        self.cycles = 0

    @staticmethod
    def _norm(value):
        return re.sub(r"\s+", " ", str(value).strip().replace("ي", "ی").replace("ك", "ک"))

    def _find(self, subject, predicate, value=None):
        rows = [b for b in self.beliefs if b.subject == subject and b.predicate == predicate]
        if value is not None:
            rows = [b for b in rows if b.value == value]
        return rows

    def observe(self, subject, predicate, value, confidence=0.8, source="observation"):
        subject, predicate, value = map(self._norm, (subject, predicate, value))
        incoming = Belief(subject, predicate, value, 1.0, max(0.01, min(0.99, float(confidence))), source)
        same = self._find(subject, predicate, value)
        if same:
            old = same[0]
            old.confidence = 1.0 - (1.0 - old.confidence) * (1.0 - incoming.confidence)
            old.frequency = (old.frequency + incoming.frequency) / 2.0
            old.updated_at = incoming.updated_at
            old.source = source
            return old
        # Revision: competing values remain visible instead of overwriting one another.
        self.beliefs.append(incoming)
        self.beliefs = self.beliefs[-self.capacity:]
        return incoming

    def revise(self, subject, predicate, value, frequency, confidence, source="revision"):
        subject, predicate, value = map(self._norm, (subject, predicate, value))
        rows = self._find(subject, predicate, value)
        if not rows:
            return self.observe(subject, predicate, value, confidence, source)
        old = rows[0]
        old.frequency = (old.frequency * old.confidence + float(frequency) * float(confidence)) / max(.01, old.confidence + float(confidence))
        old.confidence = min(.99, old.confidence + float(confidence) * .35)
        old.updated_at = time()
        old.source = source
        return old

    def competing(self, subject, predicate):
        return sorted(self._find(subject, predicate), key=lambda b: b.strength, reverse=True)

    def best(self, subject, predicate):
        rows = self.competing(subject, predicate)
        return rows[0] if rows else None

    def ask(self, subject, predicate):
        rows = self.competing(self._norm(subject), self._norm(predicate))
        if not rows:
            return ReasoningAnswer("", 0.0, status="unknown")
        best = rows[0]
        evidence = [self._format(b) for b in rows[:4]]
        status = "conflict" if len(rows) > 1 and abs(rows[0].strength - rows[1].strength) < .20 else "derived"
        return ReasoningAnswer(best.value, min(.99, best.strength), evidence, ["select-highest-support"], status)

    @staticmethod
    def _format(belief):
        return {"subject": belief.subject, "predicate": belief.predicate, "value": belief.value,
                "frequency": round(belief.frequency, 4), "confidence": round(belief.confidence, 4),
                "strength": round(belief.strength, 4), "source": belief.source}

    def derive(self, subject=None, max_hops=2):
        """Derive transitive relation chains: A-r1-B and B-r2-C -> A-r1/r2-C."""
        seed = self._norm(subject) if subject else None
        derived = []
        frontier = [b for b in self.beliefs if seed is None or b.subject == seed]
        seen = set()
        for _ in range(max(1, int(max_hops))):
            new = []
            for left in frontier:
                for right in self.beliefs:
                    if left.value != right.subject:
                        continue
                    key = (left.subject, left.predicate + ">" + right.predicate, right.value)
                    if key in seen:
                        continue
                    seen.add(key)
                    conf = left.confidence * right.confidence * .85
                    if conf < .15:
                        continue
                    derived.append(Belief(key[0], key[1], key[2], left.frequency * right.frequency, conf, "derived"))
                    new.append(derived[-1])
            frontier = new
            if not frontier:
                break
        return derived

    def ingest_task(self, task):
        self.cycles += 1
        if task.kind == "judgment":
            return self.observe(task.subject, task.predicate, task.value, task.priority, task.source)
        if task.kind == "question":
            return self.ask(task.subject, task.predicate)
        return ReasoningAnswer("", 0.0, status="goal")


_FACT_SOURCES = {
    "verified_local_seed", "explicit_user_statement", "user", "test",
    "imported", "local", "knowledge", "manual",
}

def _ingest_graph(self, graph):
    for fact in getattr(graph, "facts", []):
        if not {"subject", "predicate", "object"}.issubset(fact):
            continue
        source = str(fact.get("source", "knowledge"))
        # Learning/procedure nodes are control knowledge, not world facts.
        # They stay in the graph for learning, but must not contaminate belief retrieval.
        if source not in _FACT_SOURCES:
            continue
        self.observe(fact["subject"], fact["predicate"], fact["object"],
                     fact.get("confidence", .5), source)


def _answer_text(self, text):
    t=self._norm(text).rstrip("؟?")
    # Persian questions frequently put the predicate before the subject:
    # «پایتخت ایران چیست؟» means (ایران, پایتخت), not (پایتخت ایران, ...).
    patterns=(
        (r"^(.+?)\s+چیست$", None),
        (r"^(.+?)\s+چیه$", None),
        (r"^(.+?)\s+کجاست$", None),
        (r"^(.+?)\s+چند است$", None),
        (r"^(.+?)\s+چند(?:ه|تا) دارد$", None),
    )
    for pattern, _ in patterns:
        m=re.search(pattern,t)
        if not m: continue
        phrase=m.group(1).strip()
        direct=[b for b in self.beliefs if b.subject==phrase]
        if direct:
            best=max(direct,key=lambda b:b.strength)
            return ReasoningAnswer(best.value,best.strength,[self._format(best)],["knowledge-retrieval"],"derived")
        # Predicate-subject inversion for common local beliefs.
        candidates=[]
        for belief in self.beliefs:
            predicate=self._norm(belief.predicate).replace("_", " ")
            if predicate and (phrase == predicate or phrase.startswith(predicate + " ")):
                subject=phrase[len(predicate):].strip()
                if subject == belief.subject:
                    candidates.append(belief)
        if candidates:
            best=max(candidates,key=lambda b:b.strength)
            return ReasoningAnswer(best.value,best.strength,[self._format(best)],["predicate-subject-reversal","knowledge-retrieval"],"derived")
    # Yes/no questions can be grounded against a predicate-value belief even
    # when Persian surface syntax does not match the canonical triple exactly.
    if t.startswith("آیا"):
        body = t[3:].strip()
        candidates = []
        for belief in self.beliefs:
            surface = self._norm(f"{belief.subject} {belief.predicate} {belief.value}").replace("_", " ")
            tokens = set(re.findall(r"[آ-یA-Za-z0-9‌]+", body.lower()))
            subject_tokens = set(re.findall(r"[آ-یA-Za-z0-9‌]+", self._norm(belief.subject).lower()))
            surface_tokens = set(re.findall(r"[آ-یA-Za-z0-9‌]+", surface.lower()))
            overlap = len(tokens & surface_tokens)
            # A factual belief must anchor to the entity explicitly mentioned by
            # the user; this blocks unrelated procedural/experience records.
            if subject_tokens and (tokens & subject_tokens) and overlap >= 1:
                candidates.append((overlap, belief))
        if candidates:
            best=max(candidates,key=lambda x:(x[0],x[1].strength))[1]
            return ReasoningAnswer(f"بله؛ {best.subject} با {best.predicate} برابر با «{best.value}» ثبت شده است.",
                                   best.strength,[self._format(best)],["yes-no-grounding"],"derived")
    return ReasoningAnswer("",0.0,status="unknown")

NarsInspiredReasoner.ingest_graph=_ingest_graph
NarsInspiredReasoner.answer_text=_answer_text
