from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from pathlib import Path


@dataclass
class Observation:
    source: str
    kind: str
    content: object
    importance: float = 0.5
    confidence: float = 1.0
    novelty: float = 0.5
    goal_relevance: float = 0.5
    risk: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class CognitiveState:
    cycle_id: int = 0
    active_goal: str | None = None
    observations: list[dict] = field(default_factory=list)
    hypotheses: list[dict] = field(default_factory=list)
    predictions: list[dict] = field(default_factory=list)
    plan: dict = field(default_factory=dict)
    decision: dict = field(default_factory=dict)
    last_action: dict = field(default_factory=dict)
    last_outcome: dict = field(default_factory=dict)
    uncertainty: float = 1.0
    status: str = "idle"
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class AttentionManager:
    """Rank observations using explicit, inspectable signals."""
    def score(self, observation: Observation) -> float:
        value = (observation.importance * 0.25 + observation.confidence * 0.15
                 + observation.novelty * 0.20 + observation.goal_relevance * 0.30
                 + (1.0 - observation.risk) * 0.10)
        return round(max(0.0, min(1.0, value)), 4)

    def rank(self, observations: list[Observation]) -> list[Observation]:
        return sorted(observations, key=self.score, reverse=True)


class AutonomousController:
    """Continuous local cognition coordinator with safe read-only initiative."""
    SAFE_READ_ACTIONS = {"time_now", "project_summary", "project_files", "system_info", "memory_search"}

    def __init__(self, runtime):
        self.runtime = runtime
        self.attention = AttentionManager()
        self.state = CognitiveState()
        self.running = False
        self.state_path = self.runtime.root / "data" / "autonomy_state.json"
        self._load_state()

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                allowed = {k: v for k, v in raw.items() if k in CognitiveState.__dataclass_fields__}
                self.state = CognitiveState(**allowed)
        except (OSError, ValueError, TypeError):
            self.runtime.events.emit("autonomy_state_recovery_failed", {"path": str(self.state_path)})

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self.state), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _perceive(self) -> list[Observation]:
        observations = [
            Observation("runtime", "health", self.runtime.health(), importance=.7),
            Observation("project", "summary", self.runtime.registry.run("project_summary"), importance=.8),
            Observation("scheduler", "pending", self.runtime.scheduler.list(enabled=True), importance=.5),
        ]
        goals = self.runtime.goals.list(status="active")
        if goals:
            observations.append(Observation("goals", "active", goals, importance=.9, goal_relevance=1.0))
        return observations

    def _select_goal(self) -> str | None:
        goals = self.runtime.goals.list(status="active")
        if not goals:
            return None
        ranked = sorted(goals, key=lambda g: (float(g.get("priority", 0.5)), g.get("created_at", "")), reverse=True)
        return str(ranked[0].get("title", "")) or None

    def _safe_action(self, requested: str | None) -> str | None:
        return requested if requested in self.SAFE_READ_ACTIONS else "project_summary"

    def _observe_action(self, action_name: str) -> dict:
        tool = self.runtime.registry.get(action_name)
        if not tool or not tool.safe or tool.permission != "read":
            return {"success": False, "reason": "action not permitted for autonomous read-only mode"}
        try:
            result = self.runtime.registry.run(action_name)
            return {"success": True, "action": action_name, "result": result}
        except Exception as exc:
            return {"success": False, "action": action_name, "reason": type(exc).__name__}

    def step(self) -> dict:
        self.state.cycle_id += 1
        self.state.status = "perceiving"
        observations = self._perceive()
        ranked = self.attention.rank(observations)
        self.state.observations = [asdict(x) | {"attention": self.attention.score(x)} for x in ranked]
        self.state.active_goal = self._select_goal()

        if self.state.active_goal:
            self.state.status = "reasoning"
            cycle = self.runtime.kernel.cycle(self.state.active_goal)
            self.state.hypotheses = list(cycle.reasoning.get("evidence_inference", {}).get("hypotheses", []))
            self.state.predictions = cycle.predictions
            self.state.decision = cycle.decision or {}
            self.state.plan = {"goal": self.state.active_goal,
                               "chosen_action": self.state.decision.get("chosen"),
                               "confidence": self.state.decision.get("confidence", 0.0)}
            self.state.uncertainty = cycle.reasoning.get("evidence_inference", {}).get("uncertainty", 1.0)
            action_name = self._safe_action(self.state.decision.get("chosen"))
            self.state.status = "acting"
            self.state.last_action = {"name": action_name, "mode": "safe-read-only"}
            self.state.last_outcome = self._observe_action(action_name) if action_name else {}
            if self.state.last_outcome.get("success"):
                self.runtime.events.emit("autonomous_action_verified", self.state.last_outcome)
            else:
                self.runtime.events.emit("autonomous_action_blocked", self.state.last_outcome)
        else:
            self.state.status = "observing"
            self.state.plan = {"goal": None, "chosen_action": None}
            self.state.last_action = {"name": "project_summary", "mode": "safe-read-only"}
            self.state.last_outcome = self._observe_action("project_summary")

        self.state.status = "idle"
        self.state.updated_at = datetime.now().isoformat(timespec="seconds")
        payload = asdict(self.state)
        self.runtime.events.emit("autonomous_cycle", payload)
        self._save_state()
        return payload

    def run(self, cycles: int = 1) -> list[dict]:
        if cycles < 1:
            return []
        self.running = True
        results = []
        try:
            for _ in range(int(cycles)):
                results.append(self.step())
        finally:
            self.running = False
        return results

    def stop(self):
        self.running = False


# Compatibility boundary for the existing runtime integration.
def _persist(self):
    self._save_state()


def restore(self):
    self._load_state()


AutonomousController._persist = _persist
AutonomousController.restore = restore
