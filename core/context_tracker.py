"""Deterministic conversation context tracking for IRAN.
No model, network, embedding or external data is used.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass
class ContextItem:
    value: str
    score: float = 0.0
    turns_since_seen: int = 0
    source: str = "conversation"
    parent: str = ""


@dataclass
class ContextSnapshot:
    active_topic: str = ""
    topics: list[dict] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    short_history: list[str] = field(default_factory=list)
    long_topics: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)


class ContextTracker:
    """Recency, hierarchy, slots and bounded memory for dialogue state."""

    def __init__(self, max_topics: int = 12, short_window: int = 12):
        self.max_topics = max_topics
        self.short_window = short_window
        self.turn = 0
        self.topics: dict[str, ContextItem] = {}
        self.slots: dict[str, Any] = {}
        self.slot_history: dict[str, list[str]] = {}
        self.short_history: list[str] = []
        self.active_topic = ""
        self.conflicts: list[dict] = []

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    def observe(self, text: str, parsed: dict | None = None, resolved: str = ""):
        parsed = parsed or {}
        self.turn += 1
        text = self._text(text)
        self.short_history.append(text)
        self.short_history = self.short_history[-self.short_window:]
        for item in self.topics.values():
            item.turns_since_seen += 1
            item.score *= 0.94

        explicit = self._text(resolved)
        entities = parsed.get("entities") or []
        if explicit:
            self.touch_topic(explicit, 1.25, "reference")
        for entity in entities:
            value = entity.get("text", "") if isinstance(entity, dict) else entity
            value = self._text(value)
            if value:
                parent = self._text(entity.get("parent", "")) if isinstance(entity, dict) else ""
                self.touch_topic(value, 1.0, "entity", parent)
        goal = self._text(parsed.get("goal"))
        if goal and not explicit and not entities:
            self.touch_topic(goal, 0.55, "goal")

        for key, value in (parsed.get("slots") or {}).items():
            self.set_slot(str(key), value)
        constraints = parsed.get("constraints") or []
        if constraints:
            self.set_slot("constraints", list(constraints)[-8:])

        if explicit:
            self.active_topic = explicit
        elif entities:
            first = entities[0]
            self.active_topic = self._text(first.get("text", "") if isinstance(first, dict) else first)
        elif not self.active_topic:
            self.active_topic = self.best_topic()
        self._trim()
        return self.snapshot()

    def touch_topic(self, value: str, weight: float = 1.0, source: str = "conversation", parent: str = ""):
        value = self._text(value)
        if not value:
            return
        item = self.topics.get(value)
        if item is None:
            item = ContextItem(value=value)
            self.topics[value] = item
        item.score = min(8.0, item.score + max(0.0, float(weight)))
        item.turns_since_seen = 0
        item.source = source
        if parent:
            item.parent = parent
            if parent not in self.topics:
                self.topics[parent] = ContextItem(parent, 0.35, 0, "hierarchy")
        self.active_topic = value

    def set_slot(self, key: str, value: Any):
        key = self._text(key)
        value = self._text(value)
        if not key or not value:
            return
        old = self.slots.get(key)
        if old is not None and old != value:
            self.conflicts.append({"slot": key, "old": old, "new": value, "turn": self.turn})
            self.conflicts = self.conflicts[-12:]
        self.slots[key] = value
        history = self.slot_history.setdefault(key, [])
        if value not in history:
            history.append(value)
        self.slot_history[key] = history[-6:]

    def best_topic(self) -> str:
        if not self.topics:
            return ""
        ranked = sorted(self.topics.values(), key=lambda x: (x.score - .08*x.turns_since_seen, x.score), reverse=True)
        return ranked[0].value

    def previous_topic(self) -> str:
        ranked = sorted(self.topics.values(), key=lambda x: (x.turns_since_seen, x.score), reverse=True)
        for item in ranked:
            if item.value != self.active_topic:
                return item.value
        return ""

    def resolve(self, explicit: str = "") -> str:
        explicit = self._text(explicit)
        return explicit or self.active_topic or self.best_topic()

    def _trim(self):
        if len(self.topics) > self.max_topics:
            ranked = sorted(self.topics.items(), key=lambda kv: kv[1].score - .08*kv[1].turns_since_seen, reverse=True)
            self.topics = dict(ranked[:self.max_topics])
        if self.active_topic and self.active_topic not in self.topics:
            self.active_topic = self.best_topic()

    def snapshot(self) -> ContextSnapshot:
        rows = sorted(self.topics.values(), key=lambda x: x.score, reverse=True)
        topics = [{"value": x.value, "score": round(x.score,4), "age": x.turns_since_seen,
                   "source": x.source, "parent": x.parent} for x in rows]
        long_topics = [x.value for x in rows if x.turns_since_seen >= self.short_window // 2]
        return ContextSnapshot(self.active_topic, topics, dict(self.slots), list(self.short_history), long_topics, list(self.conflicts))

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path):
        path = Path(path)
        tracker = cls()
        if not path.exists():
            return tracker
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tracker.turn = int(data.get("turn", 0))
            tracker.active_topic = str(data.get("active_topic", ""))
            tracker.slots = dict(data.get("slots") or {})
            tracker.slot_history = dict(data.get("slot_history") or {})
            tracker.short_history = list(data.get("short_history") or [])[-tracker.short_window:]
            tracker.conflicts = list(data.get("conflicts") or [])[-12:]
            for row in data.get("topics") or []:
                value = str(row.get("value", ""))
                if value:
                    tracker.topics[value] = ContextItem(value, float(row.get("score", 0)), int(row.get("age", 0)), str(row.get("source", "conversation")), str(row.get("parent", "")))
            tracker._trim()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()
        return tracker

    def to_dict(self) -> dict:
        snap = self.snapshot()
        return {"turn": self.turn, "active_topic": snap.active_topic, "topics": snap.topics,
                "slots": snap.slots, "slot_history": self.slot_history,
                "short_history": snap.short_history, "conflicts": snap.conflicts}
