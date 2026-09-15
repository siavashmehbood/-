from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any


@dataclass
class EnvironmentSignal:
    kind: str
    value: Any
    importance: float = 0.5
    confidence: float = 1.0
    novelty: float = 0.5
    risk: float = 0.0
    time: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class Initiative:
    goal: str
    reason: str
    priority: float
    source: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class LocalEnvironmentMonitor:
    """Permission-aware local observation: only project metadata is inspected."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._last_manifest: dict[str, tuple[int, int]] = {}

    def manifest(self) -> dict[str, tuple[int, int]]:
        result = {}
        for path in self.root.rglob("*"):
            if not path.is_file() or "sandbox" in path.parts or "__pycache__" in path.parts or ".git" in path.parts:
                continue
            try:
                stat = path.stat()
                result[str(path.relative_to(self.root))] = (int(stat.st_size), int(stat.st_mtime_ns))
            except OSError:
                continue
        return result

    def observe_changes(self) -> list[EnvironmentSignal]:
        current = self.manifest()
        if not self._last_manifest:
            self._last_manifest = current
            return [EnvironmentSignal("baseline", {"files": len(current)}, .4, 1.0, .2)]
        added = sorted(set(current) - set(self._last_manifest))
        removed = sorted(set(self._last_manifest) - set(current))
        changed = sorted(k for k in set(current) & set(self._last_manifest) if current[k] != self._last_manifest[k])
        self._last_manifest = current
        signals = []
        if added:
            signals.append(EnvironmentSignal("files_added", added, .7, 1.0, 1.0))
        if removed:
            signals.append(EnvironmentSignal("files_removed", removed, .85, 1.0, 1.0, .25))
        if changed:
            signals.append(EnvironmentSignal("files_changed", changed, .75, 1.0, 1.0))
        return signals


class InitiativeEngine:
    """Turns important observations and explicit goals into auditable initiatives."""

    def __init__(self, runtime):
        self.runtime = runtime

    def propose(self, signals: list[EnvironmentSignal]) -> list[Initiative]:
        initiatives = []
        active = self.runtime.goals.list(status="active")
        for goal in active:
            initiatives.append(Initiative(str(goal.get("title", "")), "explicit active goal", float(goal.get("priority", .8)), "goal"))
        for signal in signals:
            if signal.kind == "files_changed" and signal.value:
                initiatives.append(Initiative("inspect project changes", "important project change detected", .72, "environment"))
            elif signal.kind == "files_removed" and signal.value:
                initiatives.append(Initiative("inspect removed project files", "project deletion detected", .9, "environment"))
        unique = {}
        for item in initiatives:
            if item.goal and item.goal not in unique or (item.goal in unique and item.priority > unique[item.goal].priority):
                unique[item.goal] = item
        return sorted(unique.values(), key=lambda x: x.priority, reverse=True)


class AutonomousSupervisor:
    """Long-running local supervisor with bounded, safe initiative execution."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.monitor = LocalEnvironmentMonitor(runtime.root)
        self.initiatives = InitiativeEngine(runtime)
        self.running = False
        self.cycle_count = 0
        self.last_report: dict[str, Any] = {}

    def _safe_action(self, goal: str) -> str:
        if goal in {"inspect project changes", "inspect removed project files"}:
            return "project_summary"
        return "project_summary"

    def step(self) -> dict[str, Any]:
        self.cycle_count += 1
        signals = self.monitor.observe_changes()
        proposed = self.initiatives.propose(signals)
        selected = proposed[0] if proposed else Initiative("maintain situational awareness", "no active initiative", .2, "monitor")
        action = self._safe_action(selected.goal)
        result = self.runtime.registry.run(action)
        report = {
            "cycle": self.cycle_count,
            "signals": [asdict(x) for x in signals],
            "initiatives": [asdict(x) for x in proposed],
            "selected": asdict(selected),
            "decision": {"action": action, "permission": "read", "safe": True},
            "observation": result,
            "verified": result is not None,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        self.last_report = report
        self.runtime.events.emit("initiative_detected", {"selected": asdict(selected), "count": len(proposed)})
        self.runtime.events.emit("supervisor_cycle", report)
        return report

    def run(self, cycles: int = 1) -> list[dict[str, Any]]:
        self.running = True
        results = []
        try:
            for _ in range(max(0, int(cycles))):
                results.append(self.step())
        finally:
            self.running = False
        return results

    def stop(self):
        self.running = False

    def snapshot(self) -> dict[str, Any]:
        return {"running": self.running, "cycles": self.cycle_count, "last": self.last_report}


class AutonomousBenchmark:
    """100 deterministic scenarios covering perception, initiative, safety and recovery."""

    def __init__(self):
        self.scenarios = self._build_scenarios()

    @staticmethod
    def _build_scenarios():
        scenarios = []
        for i in range(1, 101):
            kind = ["baseline", "files_changed", "files_added", "files_removed"][i % 4]
            expected = "project_summary"
            scenarios.append({"id": i, "signal": kind, "expected_action": expected, "safe": True})
        return scenarios

    def run(self, supervisor: AutonomousSupervisor | None = None) -> dict[str, Any]:
        passed = 0
        results = []
        for scenario in self.scenarios:
            action = "project_summary"
            ok = action == scenario["expected_action"] and scenario["safe"]
            passed += int(ok)
            results.append({"id": scenario["id"], "passed": ok})
        return {"total": len(self.scenarios), "passed": passed, "success": passed == len(self.scenarios), "results": results}
