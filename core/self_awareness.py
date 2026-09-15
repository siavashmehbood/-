from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any


@dataclass
class SelfState:
    """Persistent metacognitive snapshot: what the runtime believes about itself."""
    capability: dict[str, float] = field(default_factory=dict)
    capability_domains: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.5
    uncertainty: list[str] = field(default_factory=list)
    active_goal: str = ""
    strategy: str = ""
    preferred_action: str = ""
    known_limits: list[str] = field(default_factory=list)
    recent_failures: int = 0
    recent_successes: int = 0
    calibration_error: float = 0.0
    self_assessment: str = "unknown"
    last_update: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class SelfAwarenessEngine:
    """Persistent metacognition that can change the next decision, not just report it."""

    DOMAIN_MAP = {
        "project_files": "perception",
        "project_summary": "understanding",
        "memory_search": "recall",
        "reason": "reasoning",
        "plan": "planning",
        "verify": "verification",
    }

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.state = SelfState()
        self.history: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = SelfState(**data.get("state", {}))
            self.history = list(data.get("history", []))[-100:]
        except (OSError, ValueError, TypeError):
            self.state = SelfState()
            self.history = []

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"state": asdict(self.state), "history": self.history[-100:]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def observe(self, goal: str, action: str, score: float, verified: bool,
                expected: float | None = None, failure_reason: str = "") -> dict[str, Any]:
        score = max(0.0, min(1.0, float(score)))
        key = str(action)
        old = self.state.capability.get(key, 0.5)
        self.state.capability[key] = round(old * 0.7 + score * 0.3, 4)
        domain = self.DOMAIN_MAP.get(key, "execution")
        old_domain = self.state.capability_domains.get(domain, 0.5)
        self.state.capability_domains[domain] = round(old_domain * 0.7 + score * 0.3, 4)
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
        self.state.self_assessment = self._self_assessment()
        self._update_limits()
        self.state.last_update = datetime.now().isoformat(timespec="seconds")
        event = {
            "goal": str(goal), "action": key, "domain": domain, "score": score,
            "verified": bool(verified), "expected": expected,
            "failure_reason": str(failure_reason), "confidence": self.state.confidence,
            "self_assessment": self.state.self_assessment, "time": self.state.last_update,
        }
        self.history.append(event)
        self.history = self.history[-100:]
        self._save()
        return event

    def _overall_confidence(self) -> float:
        if not self.state.capability_domains:
            return 0.5
        mean = sum(self.state.capability_domains.values()) / len(self.state.capability_domains)
        penalty = min(0.25, self.state.calibration_error)
        return max(0.0, min(1.0, mean - penalty))

    def _self_assessment(self) -> str:
        domains = self.state.capability_domains
        if not domains:
            return "unknown"
        mean = sum(domains.values()) / len(domains)
        weakest = min(domains, key=domains.get)
        if self.state.calibration_error > 0.25:
            return "poorly_calibrated"
        if mean >= 0.8:
            return "strong"
        if mean >= 0.6:
            return f"functional; weakest={weakest}"
        return f"limited; weakest={weakest}"

    def _update_limits(self):
        limits = list(self.state.known_limits)
        for domain, score in self.state.capability_domains.items():
            if score < 0.4:
                marker = f"low capability in {domain}"
                if marker not in limits:
                    limits.append(marker)
        self.state.known_limits = limits[-20:]

    def reassess(self, candidates: list[str]) -> list[str]:
        """Rank actions using capability, calibration and known limits."""
        unique = list(dict.fromkeys(str(x) for x in candidates))
        def utility(action: str) -> float:
            score = self.state.capability.get(action, 0.5)
            domain = self.DOMAIN_MAP.get(action, "execution")
            if f"low capability in {domain}" in self.state.known_limits:
                score -= 0.35
            if self.state.calibration_error > 0.25:
                score -= 0.05
            return score
        return sorted(unique, key=utility, reverse=True)

    def control_next_action(self, candidates: list[str]) -> dict[str, Any]:
        ranked = self.reassess(candidates)
        chosen = ranked[0] if ranked else "project_summary"
        self.state.preferred_action = chosen
        reason = "best known capability"
        if self.state.calibration_error > 0.25:
            reason = "best capability under low calibration confidence"
        self._save()
        return {
            "preferred_action": chosen,
            "ranked_actions": ranked,
            "reason": reason,
            "confidence": self.state.confidence,
            "calibration_error": self.state.calibration_error,
        }

    def introspect(self) -> dict[str, Any]:
        strongest = sorted(self.state.capability.items(), key=lambda x: x[1], reverse=True)
        weakest = sorted(self.state.capability.items(), key=lambda x: x[1])
        domains = sorted(self.state.capability_domains.items(), key=lambda x: x[1], reverse=True)
        return {
            "self_model": asdict(self.state),
            "strongest_capabilities": strongest[:3],
            "weakest_capabilities": weakest[:3],
            "strongest_domains": domains[:3],
            "weakest_domains": domains[-3:],
            "recent_events": self.history[-5:],
            "recommendation": self._recommendation(),
        }

    def _recommendation(self) -> str:
        if self.state.calibration_error > 0.25:
            return "reduce confidence and verify predictions before acting"
        if self.state.recent_failures > self.state.recent_successes:
            return "prefer previously successful alternatives and gather more evidence"
        if self.state.known_limits:
            return "avoid weak capabilities until more evidence improves them"
        return "continue current strategy while verifying outcomes"
