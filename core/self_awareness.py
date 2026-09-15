from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SelfState:
    """Persistent metacognitive snapshot: what the runtime believes about itself."""
    capability: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.5
    uncertainty: list[str] = field(default_factory=list)
    active_goal: str = ""
    strategy: str = ""
    known_limits: list[str] = field(default_factory=list)
    recent_failures: int = 0
    recent_successes: int = 0
    calibration_error: float = 0.0
    last_update: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class SelfAwarenessEngine:
    """Turns outcomes into an explicit, behavior-relevant self model."""

    def __init__(self):
        self.state = SelfState()
        self.history: list[dict[str, Any]] = []

    def observe(self, goal: str, action: str, score: float, verified: bool,
                expected: float | None = None, failure_reason: str = "") -> dict[str, Any]:
        score = max(0.0, min(1.0, float(score)))
        key = str(action)
        old = self.state.capability.get(key, 0.5)
        self.state.capability[key] = round(old * 0.7 + score * 0.3, 4)
        self.state.active_goal = str(goal)
        self.state.strategy = key
        if verified and score >= 0.7:
            self.state.recent_successes += 1
        else:
            self.state.recent_failures += 1
        if failure_reason and failure_reason not in self.state.uncertainty:
            self.state.uncertainty.append(str(failure_reason))
        if expected is not None:
            self.state.calibration_error = round(
                self.state.calibration_error * 0.7 + abs(float(expected) - score) * 0.3, 4
            )
        self.state.confidence = round(self._overall_confidence(), 4)
        self.state.last_update = datetime.now().isoformat(timespec="seconds")
        event = {
            "goal": str(goal), "action": key, "score": score,
            "verified": bool(verified), "expected": expected,
            "failure_reason": str(failure_reason), "confidence": self.state.confidence,
            "time": self.state.last_update,
        }
        self.history.append(event)
        self.history = self.history[-100:]
        return event

    def _overall_confidence(self) -> float:
        if not self.state.capability:
            return 0.5
        mean = sum(self.state.capability.values()) / len(self.state.capability)
        penalty = min(0.25, self.state.calibration_error)
        return max(0.0, min(1.0, mean - penalty))

    def reassess(self, candidates: list[str]) -> list[str]:
        """Change future behavior using the current self-model."""
        unique = list(dict.fromkeys(str(x) for x in candidates))
        return sorted(unique, key=lambda x: self.state.capability.get(x, 0.5), reverse=True)

    def introspect(self) -> dict[str, Any]:
        strongest = sorted(self.state.capability.items(), key=lambda x: x[1], reverse=True)
        weakest = sorted(self.state.capability.items(), key=lambda x: x[1])
        return {
            "self_model": asdict(self.state),
            "strongest_capabilities": strongest[:3],
            "weakest_capabilities": weakest[:3],
            "recent_events": self.history[-5:],
            "recommendation": self._recommendation(),
        }

    def _recommendation(self) -> str:
        if self.state.calibration_error > 0.25:
            return "reduce confidence and verify predictions before acting"
        if self.state.recent_failures > self.state.recent_successes:
            return "prefer previously successful alternatives and gather more evidence"
        return "continue current strategy while verifying outcomes"
