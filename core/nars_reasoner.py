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


def _ingest_graph(self, graph):
    for fact in getattr(graph, "facts", []):
        if "subject" in fact and "predicate" in fact and "object" in fact:
            self.observe(fact["subject"], fact["predicate"], fact["object"], fact.get("confidence", .5), fact.get("source", "knowledge"))


def _answer_text(self, text):
    t=self._norm(text).rstrip("؟?")
    patterns=(
        r"^(.+?)\s+(?:چیست|چیه)$",
        r"^(.+?)\s+کجاست$",
        r"^(.+?)\s+چند است$",
        r"^(.+?)\s+چند(?:ه|تا) دارد$",
    )
    for pattern in patterns:
        m=re.search(pattern,t)
        if not m: continue
        subject=m.group(1).strip()
        candidates=[b for b in self.beliefs if b.subject==subject]
        if not candidates: continue
        best=max(candidates,key=lambda b:b.strength)
        return ReasoningAnswer(best.value,best.strength,[self._format(best)],["knowledge-retrieval"],"derived")
    return ReasoningAnswer("",0.0,status="unknown")

NarsInspiredReasoner.ingest_graph=_ingest_graph
NarsInspiredReasoner.answer_text=_answer_text
