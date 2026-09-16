"""Small symbolic working-memory buffer inspired by cognitive-architecture research.

No model or embedding service is used. Items are scored from recency, salience and
lexical overlap so the memory remains inspectable and deterministic.
"""
from dataclasses import dataclass, field
import re

@dataclass
class WorkingItem:
    content: str
    activation: float = 1.0
    salience: float = 0.5
    age: int = 0
    tags: list[str] = field(default_factory=list)

class SymbolicWorkingMemory:
    def __init__(self, capacity=32, decay=0.08):
        self.capacity = capacity
        self.decay = decay
        self.clock = 0
        self.items = []

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"\w+", str(text).lower(), re.UNICODE))

    def add(self, content, salience=0.5, tags=None):
        text = str(content).strip()
        if not text:
            return
        self.clock += 1
        for item in self.items:
            item.age += 1
            item.activation = max(0.0, item.activation - self.decay)
        self.items = [x for x in self.items if x.activation > 0.02]
        self.items.append(WorkingItem(text, 1.0, max(0.0, min(1.0, salience)), 0, list(tags or [])))
        self.items = self.items[-self.capacity:]

    def recall(self, query="", limit=8):
        q = self._tokens(query)
        ranked = []
        for item in self.items:
            overlap = len(q & self._tokens(item.content)) / max(1, len(q)) if q else 0.0
            score = 0.50 * item.activation + 0.30 * item.salience + 0.20 * overlap
            ranked.append((score, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [(round(score, 3), item.content) for score, item in ranked[:limit]]

    def snapshot(self):
        return [item.__dict__.copy() for item in self.items]
