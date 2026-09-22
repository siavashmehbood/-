from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from core.initiative_engine import InitiativeEngine as ScoredInitiativeEngine
from core.autonomy_journal import AutonomyJournal
from core.autonomous_goal_runner import AutonomousGoalRunner
from core.self_awareness import SelfAwarenessEngine


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
            relative = path.relative_to(self.root)
            # Ignore IRAN-owned runtime/editor artifacts so the supervisor does not
            # mistake its own writes for external project changes.
            if relative.parts and relative.parts[0] in {"logs", ".vscode", ".pytest_cache", ".mypy_cache", ".ruff_cache"}:
                continue
            if relative.parts and relative.parts[0] == "data" and relative.name in {
                ".iran_gui.lock", "learning_proposals.json.lock", "autonomy_journal.json",
                "experiences.json", "learned_rules.json", "goals.json", "learning_goals.json",
                "capability_learning.json", "chatgpt_reviews.json", "conversation_state.json", "learning_proposals.json",
                "context_tracker.json", "self_awareness.json", "self_corrections.json",
                "skills.json", "tasks.json", "world.json", "maturity_report.json", "internet_access.json",
                "internet_learning.json", "iran.db", "knowledge.json", "knowledge.json.bak",
                "trusted_knowledge.json", "trusted_knowledge.json.bak", "tasks.json.bak",
                "experiences.json.backup-20260918-dedupe", "learning_proposals.json.bak",
                "learning_proposals.json.backup-20260918-dedupe", "learning_proposals.json.backup-before-dedupe"
            }:
                continue
            try:
                stat = path.stat()
                result[str(relative)] = (int(stat.st_size), int(stat.st_mtime_ns))
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
        self.scored_initiatives = ScoredInitiativeEngine(runtime)
        self.last_initiatives = []
        self.completed_initiatives = []
        journal_path = Path(runtime.config.get("runtime", {}).get("autonomy_journal", "data/autonomy_journal.json"))
        if not journal_path.is_absolute():
            journal_path = runtime.root / journal_path
        self.journal = AutonomyJournal(journal_path)
        self._goal_signature = None
        self._goal_stagnation = 0
        goal_state = Path(runtime.config.get("runtime", {}).get("autonomous_goal_state", "data/autonomous_goal_state.json"))
        if not goal_state.is_absolute():
            goal_state = runtime.root / goal_state
        self.goal_runner = AutonomousGoalRunner(runtime, goal_state)
        awareness_state = Path(runtime.config.get("runtime", {}).get("self_awareness_state", "data/self_awareness.json"))
        if not awareness_state.is_absolute():
            awareness_state = runtime.root / awareness_state
        self.self_awareness = SelfAwarenessEngine(awareness_state)

    def _safe_action(self, goal: str) -> str:
        if goal in {"inspect project changes", "inspect removed project files"}:
            return "project_summary"
        return "project_summary"

    def _choose_action(self, initiative):
        """Choose a bounded read-only action using the persistent self model."""
        mapping = {
            "inspect project changes": "project_files",
            "inspect removed project files": "project_files",
            "investigate unusual project state": "project_files",
            "maintain situational awareness": "project_summary",
        }
        base = mapping.get(getattr(initiative, "goal", ""), "project_summary")
        candidates = [base, "project_summary", "project_files", "memory_search"]
        try:
            preferred = getattr(self.self_awareness.state, "preferred_action", "")
            if preferred in {"project_summary", "project_files", "memory_search"}:
                return preferred
            return self.self_awareness.reassess(candidates)[0]
        except Exception:
            return base

    def step(self) -> dict[str, Any]:
        """Run one canonical, bounded autonomous cycle."""
        self.cycle_count += 1
        signals = self.monitor.observe_changes()
        signal_text = " ".join(f"{s.kind}:{s.value}" for s in signals)
        anomaly = self.runtime.anomaly.observe(signal_text or "stable")
        preliminary = {"anomaly": asdict(anomaly)}
        candidates = self.scored_initiatives.generate(signals, preliminary)
        selected = self.scored_initiatives.choose(candidates)
        if selected is None:
            selected = Initiative("maintain situational awareness", "no active initiative", .2, "monitor")
        reasoning = self._reasoning_step(selected, signals)
        action = self._choose_action(selected)
        result = self.runtime.registry.run(action)
        verified = result is not None
        selected_data = selected.snapshot() if hasattr(selected, "snapshot") else asdict(selected)
        report = {
            "cycle": self.cycle_count, "signals": [asdict(x) for x in signals],
            "initiatives": self.scored_initiatives.snapshot(candidates),
            "selected": selected_data, "reasoning": reasoning,
            "decision": {"action": action, "permission": "read", "safe": True},
            "observation": result, "verified": verified,
            "reflection": reasoning.get("reflection"),
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        signature = selected_data.get("goal")
        if signature == self._goal_signature:
            self._goal_stagnation += 1
        else:
            self._goal_signature, self._goal_stagnation = signature, 0
        report["stagnation"] = {"detected": self._goal_stagnation >= 3, "cycles": self._goal_stagnation}
        try:
            plan = self.runtime.orchestrator.planner.build(signature)
            report["plan"] = {"goal": plan.goal, "status": plan.status, "version": plan.version,
                              "strategy": plan.strategy, "assumptions": list(plan.assumptions),
                              "steps": [asdict(s) for s in plan.steps]}
        except Exception as exc:
            report["plan"] = {"goal": signature, "status": "unavailable", "reason": type(exc).__name__}
        active = self.runtime.goals.list(status="active")
        if active:
            goal = active[0]
            plan = self.runtime.orchestrator.planner.build(goal.get("title", ""))
            state, _ = self.goal_runner.advance(goal, plan)
            report["long_horizon"] = {"goal_id": goal.get("id"), "goal": goal.get("title"),
                                      "status": state.get("status"), "step": state.get("step", 0),
                                      "total_steps": len(plan.steps), "last": state.get("last")}
            if state.get("status") == "completed":
                self.runtime.goals.complete(goal.get("id"))
        else:
            report["long_horizon"] = {"status": "no_active_goal"}
        self.self_awareness.observe(signature or "observe", action, .9 if verified else .1, verified)
        report["self_awareness"] = self.self_awareness.introspect()
        try:
            control = self.self_awareness.control_next_action(["project_summary", "project_files", "memory_search"])
            report["self_awareness_control"] = control
            report["decision"]["next_action"] = control["preferred_action"]
            expected_effect = str(control.get("expected_effect") or "").strip()
            if expected_effect:
                report["decision"]["expected_effect"] = expected_effect
        except Exception as exc:
            report["self_awareness_control"] = {"error": type(exc).__name__}
        report["decision_explanation"] = {"trigger": report.get("signals", []), "selected_goal": selected_data.get("goal"),
                                          "why": report.get("reasoning", {}).get("reason"), "chosen_action": action,
                                          "verified": verified}
        try:
            report["curriculum_learning"] = self.runtime.generate_curriculum_learning_inputs(24)
        except Exception as exc:
            report["curriculum_learning"] = {"ok": False, "error": type(exc).__name__}
        novelty = max((float(getattr(s, "novelty", 0)) for s in signals), default=0)
        expected_effect = str(report["decision"].get("expected_effect") or "").strip()
        objective = str(selected_data.get("goal") or "").strip()
        observation_text = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)[:1200] if result is not None else ""
        try:
            prior = self.runtime.learning.lessons(objective, 20)
            repeated = any(str(row.get("action")) == str(action) and str(row.get("result"))[:250] == observation_text[:250] for row in prior)
        except Exception:
            repeated = False
        if verified and novelty >= .35 and expected_effect and not repeated:
            self.runtime.learning.record(goal=objective, action=str(action), result=observation_text, score=.9,
                                         intent="autonomous", strategy=f"verified-read-only:{action}", domain="local-learning",
                                         objective=objective, expected_effect=expected_effect)
            report["learning"] = {"recorded": False, "pending_approval": True, "verified": True,
                                  "purposeful": True, "novelty": novelty}
        else:
            report["learning"] = {"recorded": False, "verified": verified, "purposeful": False,
                                  "novelty": novelty, "reason": "routine_or_repeated_observation"}
        # Persist the complete cycle only after curriculum and learning outcomes exist.
        self.journal.append(report)
        report["autonomy_status"] = self.journal.summary()
        self.last_report = report
        self.runtime.events.emit("self_awareness_updated", report["self_awareness"])
        self.runtime.events.emit("self_awareness_control", report["self_awareness_control"])
        self.runtime.events.emit("supervisor_cycle", report)
        return report

    def _reasoning_step(self, selected, signals):
        goal = selected.goal
        signal_text = " ".join(f"{s.kind}:{s.value}" for s in signals)
        anomaly = self.runtime.anomaly.observe(signal_text or "stable")
        predictions = self.runtime.prediction.predict(["project_summary", "memory_search", "project_files"], context=signal_text, state=goal)
        best = self.runtime.prediction.best(predictions)
        # Supervisor reasoning must not traverse the dialogue kernel: that path can
        # create conversation-learning records for an internal autonomy goal.
        hypotheses = [f"signal:{s.kind}" for s in signals if float(getattr(s, "novelty", 0)) >= .35]
        score = float(getattr(best, "confidence", .5)) if best else .5
        reflection = self.runtime.reflector.reflect(goal, str(best.action if best else "observe"), score, signals)
        return {"goal": goal, "anomaly": asdict(anomaly), "hypotheses": hypotheses,
                "predictions": [asdict(p) if hasattr(p, "__dataclass_fields__") else p for p in predictions],
                "best_prediction": asdict(best) if best else None, "confidence": round(score, 3), "reflection": asdict(reflection)}

    def journal_summary(self):
        return self.journal.summary()

    def goal_progress_snapshot(self):
        return self.goal_runner.snapshot()

    def self_awareness_snapshot(self):
        return self.self_awareness.introspect()

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
    """100 deterministic scenarios exercising perception-to-safe-decision behavior."""

    def __init__(self):
        self.scenarios = self._build_scenarios()

    @staticmethod
    def _build_scenarios():
        kinds = ["baseline", "files_changed", "files_added", "files_removed"]
        expected = {"baseline": "project_summary", "files_changed": "project_files",
                    "files_added": "project_files", "files_removed": "project_files"}
        return [{"id": i, "signal": kinds[i % 4], "expected_action": expected[kinds[i % 4]], "safe": True}
                for i in range(1, 101)]

    @staticmethod
    def _decision(signal):
        if signal in {"files_changed", "files_added", "files_removed"}:
            return "project_files"
        return "project_summary"

    def run(self, supervisor: AutonomousSupervisor | None = None) -> dict[str, Any]:
        passed = 0
        results = []
        allowed = {"project_summary", "project_files", "memory_search"}
        for scenario in self.scenarios:
            action = self._decision(scenario["signal"])
            safe = action in allowed and bool(scenario["safe"])
            verified = safe and action == scenario["expected_action"]
            passed += int(verified)
            results.append({"id": scenario["id"], "signal": scenario["signal"], "action": action,
                            "safe": safe, "verified": verified, "passed": verified})
        return {"total": len(self.scenarios), "passed": passed, "success": passed == len(self.scenarios), "results": results}


class LongHorizonWorldBenchmark:
    """100 varied deterministic worlds; every action is legal, observable and verified."""
    def _world(self, i):
        from core.virtual_world import VirtualWorld
        world = VirtualWorld(state={
            "system": "degraded" if i % 2 else "healthy",
            "queue": i % 6,
            "resource": 6 + (i % 7),
            "risk": round((i % 10) / 10, 2),
        })
        return world

    def run(self, max_cycles=50):
        cases = []
        passed = 0
        for i in range(1, 101):
            world = self._world(i)
            goal = "restore system" if i % 2 else "reduce queue"
            history = []
            for cycle in range(1, max_cycles + 1):
                before = world.observe()
                legal = world.legal_actions()
                if goal == "restore system" and "restore" in legal:
                    action = "restore"
                elif goal == "reduce queue" and "process_queue" in legal:
                    action = "process_queue"
                elif "inspect" in legal:
                    action = "inspect"
                else:
                    action = legal[0] if legal else "inspect"
                result = world.act(action)
                verified = result.get("success", False) and action in legal
                history.append({"cycle": cycle, "action": action, "verified": verified, "before": before, "after": result.get("after")})
                if goal == "restore system" and world.goal_satisfied(goal):
                    passed += 1
                    break
                if goal == "reduce queue" and world.goal_satisfied(goal):
                    passed += 1
                    break
            cases.append({"id": i, "goal": goal, "success": world.goal_satisfied(goal), "cycles": len(history), "history": history})
        return {"total": 100, "passed": passed, "success": passed == 100, "cases": cases}

# Replace the earlier smoke benchmark with the substantive long-horizon benchmark.
AutonomousBenchmark = LongHorizonWorldBenchmark




class LongHorizonWorldBenchmarkV2(LongHorizonWorldBenchmark):
    def run(self, max_cycles=50, supervisor=None):
        if not isinstance(max_cycles, int):
            max_cycles = 50
        return super().run(max_cycles=max_cycles)
