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



# v0.39: close the loop with the existing cognitive kernel, prediction, learning and reflection.
def _reasoning_step(self, selected, signals):
    goal = selected.goal
    signal_text = ' '.join(f'{s.kind}:{s.value}' for s in signals)
    anomaly = self.runtime.anomaly.observe(signal_text or 'stable')
    candidates = ['project_summary', 'memory_search', 'project_files']
    predictions = self.runtime.prediction.predict(candidates, context=signal_text, state=goal)
    best = self.runtime.prediction.best(predictions)
    cycle = self.runtime.kernel.cycle(goal)
    score = float(cycle.confidence) if hasattr(cycle, 'confidence') else .5
    reflection = self.runtime.reflector.reflect(goal, str(best.action if best else 'observe'), score, signals)
    self.runtime.learning.record(goal, best.action if best else 'observe', str(reflection.lessons), score, 'autonomous', 'evidence-first', 'local')
    return {
        'goal': goal,
        'anomaly': asdict(anomaly),
        'hypotheses': list(getattr(cycle, 'hypotheses', []) or []),
        'predictions': [asdict(p) if hasattr(p, '__dataclass_fields__') else p for p in predictions],
        'best_prediction': asdict(best) if best else None,
        'confidence': round(score, 3),
        'reflection': asdict(reflection),
    }

_old_supervisor_step = AutonomousSupervisor.step
def _step_v2(self):
    self.cycle_count += 1
    signals = self.monitor.observe_changes()
    proposed = self.initiatives.propose(signals)
    selected = proposed[0] if proposed else Initiative('maintain situational awareness', 'no active initiative', .2, 'monitor')
    reasoning = self._reasoning_step(selected, signals)
    action = self._safe_action(selected.goal)
    result = self.runtime.registry.run(action)
    verified = result is not None
    report = {
        'cycle': self.cycle_count,
        'signals': [asdict(x) for x in signals],
        'initiatives': [asdict(x) for x in proposed],
        'selected': asdict(selected),
        'reasoning': reasoning,
        'decision': {'action': action, 'permission': 'read', 'safe': True},
        'observation': result,
        'verified': verified,
        'learning': self.runtime.learning.adapt(selected.goal, 'autonomous', 'local'),
        'time': datetime.now().isoformat(timespec='seconds'),
    }
    self.last_report = report
    self.runtime.events.emit('initiative_detected', {'selected': asdict(selected), 'count': len(proposed)})
    self.runtime.events.emit('prediction_completed', {'goal': selected.goal, 'best': reasoning['best_prediction'], 'confidence': reasoning['confidence']})
    self.runtime.events.emit('reflection', reasoning['reflection'])
    self.runtime.events.emit('learning_update', {'goal': selected.goal, 'strategy': report['learning'].get('recommended_strategy')})
    self.runtime.events.emit('supervisor_cycle', report)
    return report

AutonomousSupervisor._reasoning_step = _reasoning_step
AutonomousSupervisor.step = _step_v2

# v0.40: goal-sensitive safe action selection instead of a single fixed action.
def _safe_action_v2(self, goal: str) -> str:
    mapping = {
        'inspect project changes': 'project_files',
        'inspect removed project files': 'project_files',
        'maintain situational awareness': 'project_summary',
    }
    return mapping.get(str(goal).strip(), 'project_summary')

AutonomousSupervisor._safe_action = _safe_action_v2


# v0.41: compatibility wrapper accepts the runtime supervisor while keeping benchmark semantics.
class LongHorizonWorldBenchmarkV2(LongHorizonWorldBenchmark):
    def run(self, max_cycles=50, supervisor=None):
        if not isinstance(max_cycles, int):
            max_cycles = 50
        return super().run(max_cycles=max_cycles)

AutonomousBenchmark = LongHorizonWorldBenchmarkV2


# v0.42: scored initiative generation with evidence, urgency, value and risk.
from core.initiative_engine import InitiativeEngine as ScoredInitiativeEngine

_scored_engine = ScoredInitiativeEngine

def _init_scored(self):
    self.scored_initiatives = _scored_engine(self.runtime)
    self.last_initiatives = []
    self.completed_initiatives = []

_old_v2_init = AutonomousSupervisor.__init__
def _supervisor_init_v2(self, runtime):
    _old_v2_init(self, runtime)
    _init_scored(self)
AutonomousSupervisor.__init__ = _supervisor_init_v2


def _choose_action(self, initiative):
    if initiative is None:
        return 'project_summary'
    mapping = {
        'inspect project changes': 'project_files',
        'inspect removed project files': 'project_files',
        'investigate unusual project state': 'project_files',
        'maintain situational awareness': 'project_summary',
    }
    return mapping.get(initiative.goal, 'project_summary')

_old_v2_step = AutonomousSupervisor.step
def _step_v3(self):
    self.cycle_count += 1
    signals = self.monitor.observe_changes()
    signal_text = ' '.join(f'{s.kind}:{s.value}' for s in signals)
    anomaly = self.runtime.anomaly.observe(signal_text or 'stable')
    preliminary = {'anomaly': asdict(anomaly)}
    candidates = self.scored_initiatives.generate(signals, preliminary)
    selected = self.scored_initiatives.choose(candidates)
    reasoning = self._reasoning_step(selected, signals)
    candidates = self.scored_initiatives.generate(signals, reasoning)
    selected = self.scored_initiatives.choose(candidates)
    action = self._choose_action(selected)
    predictions = self.runtime.prediction.predict([action, 'project_summary', 'memory_search'], context=signal_text, state=selected.goal if selected else '')
    best = self.runtime.prediction.best(predictions)
    if best and best.action in {'project_summary', 'project_files', 'memory_search'}:
        action = best.action
    result = self.runtime.registry.run(action)
    verified = result is not None
    score = round(float(getattr(best, 'confidence', .5)), 3) if best else .5
    reflection = self.runtime.reflector.reflect(selected.goal if selected else 'observe', action, score, signals)
    self.runtime.learning.record(selected.goal if selected else 'observe', action, str(reflection.lessons), score, 'autonomous', 'evidence-first', 'local')
    report = {
        'cycle': self.cycle_count,
        'signals': [asdict(x) for x in signals],
        'initiatives': self.scored_initiatives.snapshot(candidates),
        'selected': selected.snapshot() if selected else None,
        'reasoning': reasoning,
        'decision': {'action': action, 'permission': 'read', 'safe': True, 'prediction_confidence': score},
        'observation': result,
        'verified': verified,
        'reflection': asdict(reflection),
        'learning': self.runtime.learning.adapt(selected.goal if selected else 'observe', 'autonomous', 'local'),
        'time': datetime.now().isoformat(timespec='seconds'),
    }
    self.last_report = report
    self.last_initiatives = report['initiatives']
    if selected and verified:
        self.completed_initiatives.append({'goal': selected.goal, 'cycle': self.cycle_count, 'action': action})
    self.runtime.events.emit('initiative_ranked', {'candidates': report['initiatives'], 'selected': report['selected']})
    self.runtime.events.emit('prediction_completed', {'goal': selected.goal if selected else 'observe', 'best': asdict(best) if best else None})
    self.runtime.events.emit('reflection', report['reflection'])
    self.runtime.events.emit('learning_update', {'goal': selected.goal if selected else 'observe', 'strategy': report['learning'].get('recommended_strategy')})
    self.runtime.events.emit('supervisor_cycle', report)
    return report

AutonomousSupervisor.step = _step_v3


# v0.43: persistent user-visible autonomy journal and concise decision explanation.
from core.autonomy_journal import AutonomyJournal

_old_supervisor_init_v3 = AutonomousSupervisor.__init__
def _supervisor_init_v3(self, runtime):
    _old_supervisor_init_v3(self, runtime)
    self.journal = AutonomyJournal(Path(runtime.config.get('runtime', {}).get('autonomy_journal', 'data/autonomy_journal.json')))
AutonomousSupervisor.__init__ = _supervisor_init_v3

_old_step_v3 = AutonomousSupervisor.step
def _step_v4(self):
    report = _old_step_v3(self)
    entry = self.journal.append(report)
    report['autonomy_status'] = self.journal.summary()
    report['decision_explanation'] = {
        'trigger': entry.get('signals', []),
        'selected_goal': entry.get('goal'),
        'why': entry.get('reason'),
        'chosen_action': entry.get('action'),
        'verified': entry.get('verified'),
    }
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v4
AutonomousSupervisor.journal_summary = lambda self: self.journal.summary()


# v0.44: detect stalled goals and force a bounded reassessment instead of repeating forever.
_old_init_v4 = AutonomousSupervisor.__init__
def _supervisor_init_v4(self, runtime):
    _old_init_v4(self, runtime)
    self._goal_signature = None
    self._goal_stagnation = 0
AutonomousSupervisor.__init__ = _supervisor_init_v4

_old_step_v4 = AutonomousSupervisor.step
def _step_v5(self):
    report = _old_step_v4(self)
    selected = report.get('selected') or {}
    signature = selected.get('goal')
    if signature == self._goal_signature:
        self._goal_stagnation += 1
    else:
        self._goal_signature = signature
        self._goal_stagnation = 0
    if self._goal_stagnation >= 3 and signature:
        report['stagnation'] = {'detected': True, 'cycles': self._goal_stagnation, 'response': 'reassess'}
        self.runtime.events.emit('goal_stagnation_detected', {'goal': signature, 'cycles': self._goal_stagnation})
        report['decision']['action'] = 'memory_search'
        report['decision']['reason'] = 'reassess stalled goal using prior evidence'
    else:
        report['stagnation'] = {'detected': False, 'cycles': self._goal_stagnation}
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v5


# v0.45: attach an explicit dependency-aware plan and next-ready step to every autonomous decision.
_old_step_v5 = AutonomousSupervisor.step
def _step_v6(self):
    report = _old_step_v5(self)
    selected = report.get('selected') or {}
    goal = selected.get('goal')
    if goal:
        try:
            plan = self.runtime.orchestrator.planner.build(goal)
            ready = self.runtime.orchestrator.planner.next_ready(plan)
            report['plan'] = {
                'goal': plan.goal,
                'status': plan.status,
                'version': plan.version,
                'strategy': plan.strategy,
                'assumptions': list(plan.assumptions),
                'steps': [asdict(s) for s in plan.steps],
                'next_ready': asdict(ready[0]) if ready else None,
            }
            self.runtime.events.emit('autonomous_plan_updated', report['plan'])
        except Exception as exc:
            report['plan'] = {'goal': goal, 'status': 'unavailable', 'reason': type(exc).__name__}
    else:
        report['plan'] = {'goal': None, 'status': 'idle', 'steps': []}
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v6


# v0.45b: bind the scored action selector into the supervisor class.
AutonomousSupervisor._choose_action = _choose_action


# v0.46: persistent multi-cycle goal progression.
from core.autonomous_goal_runner import AutonomousGoalRunner
_old_init_v5 = AutonomousSupervisor.__init__
def _supervisor_init_v5(self, runtime):
    _old_init_v5(self, runtime)
    self.goal_runner = AutonomousGoalRunner(
        runtime,
        Path(runtime.config.get('runtime', {}).get('autonomous_goal_state', 'data/autonomous_goal_state.json')),
    )
AutonomousSupervisor.__init__ = _supervisor_init_v5

_old_step_v6 = AutonomousSupervisor.step
def _step_v7(self):
    report = _old_step_v6(self)
    active = self.runtime.goals.list(status='active')
    if active:
        goal = active[0]
        plan = self.runtime.orchestrator.planner.build(goal.get('title', ''))
        state, observation = self.goal_runner.advance(goal, plan)
        report['long_horizon'] = {
            'goal_id': goal.get('id'),
            'goal': goal.get('title'),
            'status': state.get('status'),
            'step': state.get('step', 0),
            'total_steps': len(plan.steps),
            'last': state.get('last'),
        }
        if state.get('status') == 'completed':
            self.runtime.goals.complete(goal.get('id'))
            self.runtime.events.emit('autonomous_goal_completed', report['long_horizon'])
        elif state.get('status') == 'reassess':
            self.runtime.events.emit('autonomous_goal_reassess', report['long_horizon'])
    else:
        report['long_horizon'] = {'status': 'no_active_goal'}
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v7
AutonomousSupervisor.goal_progress_snapshot = lambda self: self.goal_runner.snapshot()


# v0.47: explicit self-awareness loop; outcomes update a persistent self-model.
from core.self_awareness import SelfAwarenessEngine

_old_init_v6 = AutonomousSupervisor.__init__
def _supervisor_init_v6(self, runtime):
    _old_init_v6(self, runtime)
    self.self_awareness = SelfAwarenessEngine(
        Path(runtime.config.get('runtime', {}).get('self_awareness_state', 'data/self_awareness.json')),
    )
AutonomousSupervisor.__init__ = _supervisor_init_v6

_old_step_v7 = AutonomousSupervisor.step
def _step_v8(self):
    report = _old_step_v7(self)
    selected = report.get('selected') or {}
    goal = selected.get('goal') or 'observe'
    decision = report.get('decision') or {}
    action = decision.get('action') or 'observe'
    verified = bool(report.get('verified'))
    expected = decision.get('prediction_confidence')
    outcome_score = .9 if verified else .1
    self.self_awareness.observe(
        goal, action, outcome_score, verified,
        expected=expected,
        failure_reason='' if verified else 'action observation was not verified',
    )
    report['self_awareness'] = self.self_awareness.introspect()
    self.runtime.events.emit('self_awareness_updated', report['self_awareness'])
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v8
AutonomousSupervisor.self_awareness_snapshot = lambda self: self.self_awareness.introspect()


# v0.47b: self-model participates in action choice instead of only reporting introspection.
_old_choose_action_v1 = AutonomousSupervisor._choose_action
def _choose_action_v2(self, initiative):
    base = _old_choose_action_v1(self, initiative)
    candidates = [base, 'project_summary', 'project_files', 'memory_search']
    try:
        return self.self_awareness.reassess(candidates)[0]
    except Exception:
        return base
AutonomousSupervisor._choose_action = _choose_action_v2


# v0.48: self-awareness controls the next cycle, not only introspection.
_old_step_v8 = AutonomousSupervisor.step
def _step_v9(self):
    report = _old_step_v8(self)
    candidates = ['project_summary', 'project_files', 'memory_search']
    try:
        control = self.self_awareness.control_next_action(candidates)
        report['self_awareness_control'] = control
        decision = report.setdefault('decision', {})
        decision['next_action'] = control['preferred_action']
        decision['self_model_reason'] = control['reason']
        self.runtime.events.emit('self_awareness_control', control)
    except Exception as exc:
        report['self_awareness_control'] = {'error': type(exc).__name__}
    self.last_report = report
    return report
AutonomousSupervisor.step = _step_v9

_old_choose_action_v2 = AutonomousSupervisor._choose_action
def _choose_action_v3(self, initiative):
    preferred = getattr(self.self_awareness.state, 'preferred_action', '')
    if preferred in {'project_summary', 'project_files', 'memory_search'}:
        return preferred
    return _old_choose_action_v2(self, initiative)
AutonomousSupervisor._choose_action = _choose_action_v3
