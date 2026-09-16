"""AtomSpace-inspired typed knowledge layer for IRAN.

This is a clean-room, model-free adaptation of typed atoms, links, truth values,
and pattern-oriented retrieval. Persistence remains delegated to KnowledgeGraph.
"""
from dataclasses import dataclass, field
from time import time


@dataclass(frozen=True)
class TruthValue:
    frequency: float = 1.0
    confidence: float = 0.5

    @property
    def strength(self):
        return self.frequency * self.confidence


@dataclass(frozen=True)
class Atom:
    name: str
    atom_type: str = "ConceptNode"
    truth: TruthValue = field(default_factory=TruthValue)
    source: str = "internal"


@dataclass(frozen=True)
class Link:
    relation: str
    source: str
    target: str
    truth: TruthValue = field(default_factory=TruthValue)
    source_tag: str = "internal"


class AtomSpace:
    """Typed graph facade over IRAN's durable KnowledgeGraph."""

    def __init__(self, knowledge_graph):
        self.graph = knowledge_graph
        self.created = time()

    @staticmethod
    def _norm(value):
        return " ".join(str(value).strip().replace("ي", "ی").replace("ك", "ک").split())

    def add_node(self, name, atom_type="ConceptNode", confidence=1.0, source="internal"):
        name = self._norm(name)
        self.graph.add_node(name, atom_type, {"name": name}, confidence, source)
        return Atom(name, atom_type, TruthValue(1.0, float(confidence)), source)

    def add_link(self, relation, source, target, frequency=1.0, confidence=0.8, source_tag="internal"):
        source, target, relation = map(self._norm, (source, target, relation))
        self.add_node(source, "ConceptNode", confidence, source_tag)
        self.add_node(target, "ConceptNode", confidence, source_tag)
        self.graph.add_edge(source, relation, target, confidence, source_tag, source_tag)
        return Link(relation, source, target, TruthValue(float(frequency), float(confidence)), source_tag)

    def observe_fact(self, subject, predicate, value, confidence=0.8, source="knowledge"):
        self.graph.add_fact(subject, predicate, value, confidence, source)
        return self.add_link(predicate, subject, value, confidence=confidence, source_tag=source)

    def atoms(self, atom_type=None, limit=100):
        rows = []
        for fact in self.graph.facts:
            if fact.get("predicate") != "type" or not str(fact.get("subject", "")).startswith("node:"):
                continue
            if atom_type and fact.get("object") != atom_type:
                continue
            rows.append(Atom(str(fact["subject"])[5:], fact["object"],
                             TruthValue(1.0, float(fact.get("confidence", .5))), fact.get("source", "internal")))
        return rows[:int(limit)]

    def links(self, relation=None, source=None, target=None, limit=100):
        rows = []
        for fact in self.graph.facts:
            if not str(fact.get("subject", "")).startswith("node:"):
                continue
            if fact.get("predicate") == "type" or fact.get("predicate") == "data":
                continue
            s = str(fact.get("subject"))[5:]
            t = str(fact.get("object", ""))[5:] if str(fact.get("object", "")).startswith("node:") else str(fact.get("object"))
            if relation and fact.get("predicate") != relation: continue
            if source and s != self._norm(source): continue
            if target and t != self._norm(target): continue
            rows.append(Link(fact.get("predicate", ""), s, t,
                              TruthValue(1.0, float(fact.get("confidence", .5))), fact.get("source", "internal")))
        return rows[:int(limit)]

    def query(self, relation=None, source=None, target=None, min_confidence=0.0, limit=50):
        return [x for x in self.links(relation, source, target, limit=1000)
                if x.truth.confidence >= float(min_confidence)][:int(limit)]

    def neighbors(self, name, relation=None, limit=50):
        return self.query(relation=relation, source=name, limit=limit)

    def infer(self, name, depth=2, min_confidence=.15, limit=50):
        """Pattern-free multi-hop traversal with multiplicative truth confidence."""
        frontier=[(self._norm(name), 1.0, 0)]
        seen=set(); out=[]
        while frontier and len(out) < int(limit):
            node, score, level = frontier.pop(0)
            if level >= int(depth): continue
            for edge in self.links(source=node, limit=1000):
                new_score = score * edge.truth.confidence
                key=(edge.source, edge.relation, edge.target)
                if key in seen or new_score < float(min_confidence): continue
                seen.add(key)
                out.append({"link": edge, "confidence": round(new_score, 4), "hop": level + 1})
                frontier.append((edge.target, new_score, level + 1))
        return sorted(out, key=lambda x:x["confidence"], reverse=True)[:int(limit)]

    def snapshot(self):
        return {"atoms": len(self.atoms(limit=100000)), "links": len(self.links(limit=100000)),
                "facts": len(self.graph.facts)}


    def sync(self):
        """Materialize durable facts as typed atoms/links without changing their truth."""
        for fact in self.graph.facts:
            subject = fact.get("subject")
            predicate = fact.get("predicate")
            target = fact.get("object")
            if not subject or not predicate or target is None:
                continue
            if str(subject).startswith("node:"):
                continue
            self.observe_fact(subject, predicate, target, float(fact.get("confidence", .5)), fact.get("source", "knowledge"))
        return self.snapshot()

    def sync(self):
        """Materialize a stable snapshot of durable facts as typed atoms/links."""
        facts = list(self.graph.facts)
        for fact in facts:
            subject = fact.get("subject")
            predicate = fact.get("predicate")
            target = fact.get("object")
            if not subject or not predicate or target is None or str(subject).startswith("node:"):
                continue
            self.observe_fact(subject, predicate, target, float(fact.get("confidence", .5)), fact.get("source", "knowledge"))
        return self.snapshot()


# v0.39: sync is a read-only view refresh. Durable KnowledgeGraph facts are already
# the source of truth; rebuilding them through add_fact would rewrite the whole JSON
# graph once per atom and make every dialogue turn unnecessarily expensive.
def _sync_read_only(self):
    return self.snapshot()

AtomSpace.sync = _sync_read_only
