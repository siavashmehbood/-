from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InitiativeCandidate:
    goal: str
    reason: str
    priority: float
    urgency: float
    confidence: float
    expected_value: float
    risk: float
    next_action: str
    evidence: list[Any] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def score(self) -> float:
        return round(
            self.priority * .25
            + self.urgency * .20
            + self.confidence * .20
            + self.expected_value * .25
            - self.risk * .10,
            4,
        )

    def snapshot(self):
        data = asdict(self)
        data["score"] = self.score
        return data


class InitiativeEngine:
    """Generates, ranks and suppresses autonomous work instead of blindly reacting."""

    def __init__(self, runtime):
        self.runtime = runtime

    def _explicit_goals(self):
        result = []
        for goal in self.runtime.goals.list(status="active"):
            title = str(goal.get("title", "")).strip()
            if title:
                result.append(InitiativeCandidate(title, "explicit active goal", float(goal.get("priority", .8)), .8, 1.0, .9, .05, "plan_goal"))
        return result

    def generate(self, signals, reasoning=None):
        candidates = self._explicit_goals()
        for signal in signals:
            if signal.kind == "files_removed":
                candidates.append(InitiativeCandidate("inspect removed project files", "deletion detected", .9, .9, signal.confidence, .8, .25, "project_files", signal.value))
            elif signal.kind in {"files_changed", "files_added"}:
                candidates.append(InitiativeCandidate("inspect project changes", "project change detected", .72, .65, signal.confidence, .72, .05, "project_files", signal.value))
        if reasoning and reasoning.get("anomaly", {}).get("score", 0) >= .65:
            candidates.append(InitiativeCandidate("investigate unusual project state", "anomaly above threshold", .82, .8, reasoning["anomaly"].get("score", .5), .85, .15, "project_files", [reasoning["anomaly"]]))
        if not candidates:
            candidates.append(InitiativeCandidate("maintain situational awareness", "no higher-value work detected", .2, .1, .9, .2, .0, "project_summary"))
        unique = {}
        for item in candidates:
            old = unique.get(item.goal)
            if old is None or item.score > old.score:
                unique[item.goal] = item
        return sorted(unique.values(), key=lambda x: x.score, reverse=True)

    def choose(self, candidates):
        return candidates[0] if candidates else None

    def snapshot(self, candidates):
        return [c.snapshot() for c in candidates]
