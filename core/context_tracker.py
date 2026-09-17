"""Deterministic short/long conversation context tracking for IRAN.

No model, network, embedding or external data is used. The tracker keeps
recency-weighted topics, explicit slots and a bounded short-term turn window.
It is deliberately independent from the answer generator so context can be
verified and tested before realization.
"""
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path
import json


@dataclass
class ContextItem:
    value: str
    score: float = 0.0
    turns_since_seen: int = 0
    source: str = "conversation"


@dataclass
class ContextSnapshot:
    active_topic: str = ""
    topics: list[dict] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    short_history: list[str] = field(default_factory=list)


class ContextTracker:
    """Recency + explicitness tracker for dialogue state."""

    def __init__(self, max_topics: int = 12, short_window: int = 12):
        self.max_topics = max_topics
        self.short_window = short_window
        self.turn = 0
        self.topics: dict[str, ContextItem] = {}
        self.slots: dict[str, Any] = {}
        self.short_history: list[str] = []
        self.active_topic = ""

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
        if explicit:
            self.touch_topic(explicit, weight=1.0, source="reference")

        entities = parsed.get("entities") or []
        for entity in entities:
            value = entity.get("text", "") if isinstance(entity, dict) else entity
            value = self._text(value)
            if value:
                self.touch_topic(value, weight=0.9, source="entity")

        goal = self._text(parsed.get("goal"))
        if goal and not explicit and not entities:
            # A goal is a weak topic signal; explicit references always win.
            self.touch_topic(goal, weight=0.55, source="goal")

        for key, value in (parsed.get("slots") or {}).items():
            value = self._text(value)
            if value:
                self.slots[str(key)] = value

        constraints = parsed.get("constraints") or []
        if constraints:
            self.slots["constraints"] = list(constraints)[-8:]

        if explicit:
            self.active_topic = explicit
        elif entities:
            self.active_topic = self._text(entities[0].get("text", "") if isinstance(entities[0], dict) else entities[0])
        elif not self.active_topic:
            self.active_topic = self.best_topic()

        self._trim()
        return self.snapshot()

    def touch_topic(self, value: str, weight: float = 1.0, source: str = "conversation"):
        value = self._text(value)
        if not value:
            return
        item = self.topics.get(value)
        if item is None:
            item = ContextItem(value=value)
            self.topics[value] = item
        item.score = min(5.0, item.score + max(0.0, float(weight)))
        item.turns_since_seen = 0
        item.source = source
        self.active_topic = value

    def best_topic(self) -> str:
        if not self.topics:
            return ""
        ranked = sorted(self.topics.values(), key=lambda x: (x.score - 0.08 * x.turns_since_seen, x.score), reverse=True)
        return ranked[0].value

    def resolve(self, explicit: str = "") -> str:
        explicit = self._text(explicit)
        if explicit:
            return explicit
        return self.active_topic or self.best_topic()

    def _trim(self):
        if len(self.topics) > self.max_topics:
            ranked = sorted(self.topics.items(), key=lambda kv: kv[1].score - 0.08 * kv[1].turns_since_seen, reverse=True)
            self.topics = dict(ranked[: self.max_topics])
        if self.active_topic and self.active_topic not in self.topics:
            self.active_topic = self.best_topic()

    def snapshot(self) -> ContextSnapshot:
        topics = [
            {"value": item.value, "score": round(item.score, 4), "age": item.turns_since_seen, "source": item.source}
            for item in sorted(self.topics.values(), key=lambda x: x.score, reverse=True)
        ]
        return ContextSnapshot(
            active_topic=self.active_topic,
            topics=topics,
            slots=dict(self.slots),
            short_history=list(self.short_history),
        )

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"turn": self.turn, **self.to_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")

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
            tracker.short_history = list(data.get("short_history") or [])[-tracker.short_window:]
            for row in data.get("topics") or []:
                value = str(row.get("value", ""))
                if value:
                    tracker.topics[value] = ContextItem(value, float(row.get("score", 0)), int(row.get("age", 0)), str(row.get("source", "conversation")))
            tracker._trim()
        except (OSError, ValueError, TypeError):
            return cls()
        return tracker
    def to_dict(self) -> dict:
        snap = self.snapshot()
        return {
            "turn": self.turn,
            "active_topic": snap.active_topic,
            "topics": snap.topics,
            "slots": snap.slots,
            "short_history": snap.short_history,
        }
