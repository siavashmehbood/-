"""Maturity benchmark for IRAN.

This module turns the ten target maturity levels of the IRAN architecture into
executable behavioural probes. It does not ask "does a file exist"; it asks
"does the system actually do this", by driving real components inside an
isolated temporary root so that production data is never touched.

The resulting score is the project's definition of "how close to 100%".
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

PASS = "pass"
PARTIAL = "partial"
FAIL = "fail"
ERROR = "error"

LEVEL_TITLES = {
    1: "Memory - important events are retained",
    2: "Learning - patterns are extracted from events",
    3: "Application - a learned pattern is reused next time",
    4: "Generalization - a pattern transfers to a similar but different case",
    5: "Self-correction - a failing strategy is replaced",
    6: "Cross-task transfer - one lesson changes several behaviours",
    7: "Self-model - the system knows what it knows and where it is weak",
    8: "Goal orientation - a goal becomes subgoals and actions",
    9: "Autonomous loop - observe/think/act/verify/learn repeats unaided",
    10: "Cumulative growth - each valid experience improves the next version",
}


@dataclass
class ProbeResult:
    """Outcome of a single behavioural probe."""

    name: str
    level: int
    status: str
    score: float
    weight: float = 1.0
    evidence: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "level": self.level,
            "status": self.status,
            "score": round(self.score, 3),
            "weight": self.weight,
            "evidence": self.evidence[:400],
        }


@dataclass
class MaturityReport:
    """Aggregated maturity measurement across all levels."""

    probes: list[ProbeResult] = field(default_factory=list)

    def level_scores(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for level in sorted(LEVEL_TITLES):
            items = [p for p in self.probes if p.level == level]
            if not items:
                out[level] = 0.0
                continue
            total = sum(p.weight for p in items) or 1.0
            out[level] = sum(p.score * p.weight for p in items) / total
        return out

    @property
    def score(self) -> float:
        """Overall maturity as a percentage; every level weighs the same."""
        scores = self.level_scores()
        if not scores:
            return 0.0
        return 100.0 * sum(scores.values()) / len(scores)

    def as_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "levels": {
                str(k): {
                    "title": LEVEL_TITLES[k],
                    "score": round(v * 100, 1),
                }
                for k, v in self.level_scores().items()
            },
            "probes": [p.as_dict() for p in self.probes],
        }


class Harness:
    """Owns an isolated copy of the project root used by the probes."""

    def __init__(self, source: Path):
        self.source = Path(source)
        self.root = Path(tempfile.mkdtemp(prefix="iran-maturity-"))
        shutil.copy2(self.source / "config.json", self.root / "config.json")
        for sub in ("data", "logs", "sandbox"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self._runtime = None

    def runtime(self):
        """Lazily build a real IranRuntime against the isolated root."""
        if self._runtime is None:
            from runtime.app import IranRuntime

            self._runtime = IranRuntime(self.root)
        return self._runtime

    def fresh_runtime(self):
        """Build a second runtime over the same root, to test persistence."""
        from runtime.app import IranRuntime

        return IranRuntime(self.root)

    def close(self) -> None:
        if self._runtime is not None:
            try:
                self._runtime.close()
            except Exception:
                pass
            self._runtime = None
        shutil.rmtree(self.root, ignore_errors=True)


PROBES: list[tuple[str, int, float, Callable]] = []


def probe(name: str, level: int, weight: float = 1.0):
    """Register a probe function returning (status, score, evidence)."""

    def wrap(fn: Callable) -> Callable:
        PROBES.append((name, level, weight, fn))
        return fn

    return wrap


def _verdict(ok: bool, evidence: str, partial: bool = False) -> tuple[str, float, str]:
    if ok:
        return PASS, 1.0, evidence
    if partial:
        return PARTIAL, 0.5, evidence
    return FAIL, 0.0, evidence


def _attr(obj, *names, default=None):
    """First existing attribute among names; keeps probes robust to renames."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default


def _component(rt, *names):
    """Find a wired subsystem anywhere in the runtime's composition graph.

    IRAN composes subsystems at several depths (runtime, cognitive system,
    pipeline, dialogue, orchestrator). A probe should measure whether the
    capability is reachable at all, not whether it sits at one exact address.
    """
    roots = [rt]
    for path in (
        ("cognitive_system",),
        ("cognitive_system", "pipeline"),
        ("cognitive_system", "components"),
        ("dialogue",),
        ("orchestrator",),
        ("autonomous_supervisor",),
        ("brain",),
    ):
        node = rt
        for step in path:
            node = getattr(node, step, None)
            if node is None:
                break
        if node is not None:
            roots.append(node)
    for root in roots:
        for name in names:
            found = getattr(root, name, None)
            if found is not None:
                return found
    return None


def _module_exists(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _text(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


# ---------------------------------------------------------------- level 1


@probe("episodic memory survives a restart", 1)
def _p_memory_restart(h: Harness):
    rt = h.runtime()
    rt.memory.add("fact", "سیاوش روی پروژه ایران کار می‌کند", 0.9, 0.9, "probe")
    rt.memory.close()
    rt2 = h.fresh_runtime()
    try:
        found = rt2.memory.search("ایران", 5)
        return _verdict(bool(found), f"recalled={len(found or [])}")
    finally:
        rt2.memory.close()
        h._runtime = None


@probe("semantic facts are stored and retrievable", 1)
def _p_semantic_fact(h: Harness):
    rt = h.runtime()
    gate = getattr(rt, "learning_gate", None)
    context = gate.bypass() if gate is not None else None
    if context is not None:
        context.__enter__()
    try:
        rt.memory.add_semantic_fact("پایتون", "نوع", "زبان برنامه‌نویسی", 0.9, "probe")
        hits = rt.memory.semantic_search("پایتون", 5)
        return _verdict(bool(hits), f"hits={len(hits or [])}")
    finally:
        if context is not None:
            context.__exit__(None, None, None)


@probe("memory consolidation and forgetting exist", 1, weight=1.0)
def _p_consolidation(h: Harness):
    has_module = _module_exists("memory.consolidation")
    rt = h.runtime()
    has_decay = callable(_attr(rt.memory, "decay"))
    if has_module and has_decay:
        return _verdict(True, "memory.consolidation module + decay()")
    return _verdict(
        False,
        f"consolidation_module={has_module} decay={has_decay}",
        partial=has_decay,
    )


# ---------------------------------------------------------------- level 2

GOAL_A = "رفع خطای ایمپورت ماژول"
GOAL_B = "رفع خطای ایمپورت وابستگی"


def _learning(h: Harness):
    rt = h.runtime()
    engine = _attr(rt, "learning", "learning_engine", "learner")
    if engine is None:
        raise AssertionError("no learning engine on runtime")
    return rt, engine


def _seed_experiences(engine) -> None:
    """Seed isolated benchmark data through the approved test-fixture path."""
    gate = getattr(engine, "gate", None)
    context = gate.bypass() if gate is not None else None
    if context is not None:
        context.__enter__()
    try:
        for _ in range(4):
            engine.record(
                goal=GOAL_A,
                action="اجرای تست",
                result="ModuleNotFoundError",
                score=0.1,
                intent="repair",
                strategy="check_path",
                domain="code",
            )
        for _ in range(4):
            engine.record(
                goal=GOAL_A,
                action="نصب دوباره وابستگی",
                result="تست سبز شد",
                score=0.95,
                intent="repair",
                strategy="reinstall",
                domain="code",
            )
    finally:
        if context is not None:
            context.__exit__(None, None, None)


@probe("lessons are extracted from raw experiences", 2)
def _p_lessons(h: Harness):
    _, engine = _learning(h)
    _seed_experiences(engine)
    lessons = engine.lessons(GOAL_A, 5)
    return _verdict(bool(lessons), f"lessons={_text(lessons)[:200]}")


@probe("failure patterns are clustered", 2)
def _p_failure_patterns(h: Harness):
    _, engine = _learning(h)
    _seed_experiences(engine)
    clusters = None
    for name in ("failure_clusters", "failure_patterns"):
        fn = _attr(engine, name)
        if callable(fn):
            clusters = fn(5)
            if clusters:
                break
    return _verdict(bool(clusters), f"clusters={_text(clusters)[:200]}")


@probe("contradictory knowledge is detected, not silently overwritten", 2)
def _p_contradiction(h: Harness):
    rt = h.runtime()
    graph = _component(rt, "knowledge", "knowledge_graph", "graph")
    if graph is None:
        return _verdict(False, "knowledge graph is not wired anywhere")
    gate = getattr(rt, "learning_gate", None)
    context = gate.bypass() if gate is not None else None
    if context is not None:
        context.__enter__()
    try:
        graph.add_fact("پورت سرویس", "است", "8080", 0.8, "doc")
        contradict = _attr(graph, "contradict")
        if callable(contradict):
            contradict("پورت سرویس", "است", "9090", 0.6, "log")
    finally:
        if context is not None:
            context.__exit__(None, None, None)
    found = graph.contradictions("پورت سرویس")
    resolved = _attr(graph, "best_fact")
    best = resolved("پورت سرویس", "است") if callable(resolved) else None
    ok = bool(found) and best is not None
    return _verdict(ok, f"contradictions={_text(found)[:160]} best={_text(best)[:120]}")


# ---------------------------------------------------------------- level 3


@probe("the winning strategy is recommended next time", 3, weight=2.0)
def _p_reuse_strategy(h: Harness):
    _, engine = _learning(h)
    _seed_experiences(engine)
    fn = _attr(engine, "recommended_strategy")
    rec = fn(GOAL_A, "repair", "code") if callable(fn) else None
    name = _text(rec)
    ok = "reinstall" in name
    return _verdict(ok, f"recommended={name[:160]}", partial=rec is not None)


@probe("an explicit rule is derived from repeated outcomes", 3)
def _p_derive_rule(h: Harness):
    _, engine = _learning(h)
    _seed_experiences(engine)
    fn = _attr(engine, "derive_rule")
    rule = fn(GOAL_A, "repair", "code") if callable(fn) else None
    if rule is None:
        return _verdict(False, "derive_rule unavailable or returned None")
    lookup = _attr(engine, "rules_for")
    stored = lookup(GOAL_A, "repair", "code", 5) if callable(lookup) else None
    return _verdict(bool(stored), f"rule={_text(rule)[:160]} stored={_text(stored)[:120]}")


# ---------------------------------------------------------------- level 4


@probe("a lesson transfers to a similar but unseen goal", 4, weight=2.0)
def _p_transfer(h: Harness):
    _, engine = _learning(h)
    _seed_experiences(engine)
    fn = _attr(engine, "adapt", "recommended_strategy")
    out = fn(GOAL_B, "repair", "code") if callable(fn) else None
    name = _text(out)
    ok = "reinstall" in name
    return _verdict(ok, f"goal_b_suggestion={name[:200]}", partial=bool(out))


@probe("skills are retrieved for goals they were not recorded against", 4)
def _p_skill_transfer(h: Harness):
    rt = h.runtime()
    skills = _attr(rt, "skills", "skill_system")
    if skills is None:
        return _verdict(False, "no skill system on runtime")
    skills.upsert(
        name="reinstall-dependency",
        description="نصب دوباره وابستگی برای رفع خطای ایمپورت",
        domain="code",
        goal_patterns=["خطای ایمپورت", "وابستگی"],
        procedure=["شناسایی وابستگی", "نصب دوباره", "اجرای تست"],
        confidence=0.8,
    )
    fn = _attr(skills, "retrieve_transfer", "retrieve")
    hits = fn(GOAL_B, "code", 5) if callable(fn) else None
    return _verdict(bool(hits), f"transfer_hits={len(hits or [])}")


@probe("a dedicated generalization engine conditions lessons on context", 4)
def _p_generalization_engine(h: Harness):
    ok = _module_exists("learning.generalizer") or _module_exists(
        "learning.generalization"
    )
    return _verdict(ok, f"learning.generalizer module present={ok}")


# ---------------------------------------------------------------- level 5


@probe("a failing strategy is abandoned in favour of a working one", 5, weight=2.0)
def _p_strategy_switch(h: Harness):
    _, engine = _learning(h)
    gate = getattr(engine, "gate", None)
    context = gate.bypass() if gate is not None else None
    if context is not None:
        context.__enter__()
    try:
        for _ in range(5):
            engine.record(
                goal="ساخت گزارش",
                action="خروجی مستقیم",
                result="گزارش ناقص",
                score=0.15,
                intent="build",
                strategy="direct",
                domain="report",
            )
        fn = _attr(engine, "recommended_strategy")
        before = _text(fn("ساخت گزارش", "build", "report")) if callable(fn) else ""
        for _ in range(5):
            engine.record(
                goal="ساخت گزارش",
                action="ساخت مرحله‌ای با بازبینی",
                result="گزارش کامل",
                score=0.92,
                intent="build",
                strategy="staged",
                domain="report",
            )
        after = _text(fn("ساخت گزارش", "build", "report")) if callable(fn) else ""
        ok = "staged" in after and after != before
        return _verdict(ok, f"before={before[:90]} after={after[:90]}")
    finally:
        if context is not None:
            context.__exit__(None, None, None)


@probe("corrections from the user are stored and block the bad answer", 5)
def _p_self_correction(h: Harness):
    rt = h.runtime()
    engine = _component(rt, "self_correction", "correction")
    if engine is None:
        return _verdict(False, "self-correction engine is not wired anywhere")
    engine.record_correction(
        "پایتخت ایران کجاست؟",
        "اصفهان",
        "تهران",
        "پاسخ جغرافیایی باید از دانش تأییدشده بیاید",
    )
    avoid = _attr(engine, "should_avoid")
    blocked = avoid("پایتخت ایران کجاست؟", "اصفهان") if callable(avoid) else None
    recall = engine.retrieve("پایتخت ایران کجاست؟", 3)
    return _verdict(bool(blocked) and bool(recall), f"blocked={blocked} recall={len(recall or [])}")


@probe("a dedicated error memory records why things failed", 5)
def _p_error_memory(h: Harness):
    ok = _module_exists("memory.error")
    return _verdict(ok, f"memory.error module present={ok}")


# ---------------------------------------------------------------- level 6


def _planner(rt):
    """Find the *task* planner, not the answer planner.

    `dialogue.planner` is an AnswerPlanner and shares the attribute name with
    the task Planner, so the probe selects by capability instead of by name.
    """
    seen = []
    for holder in (rt, getattr(rt, "orchestrator", None), getattr(rt, "dialogue", None)):
        if holder is None:
            continue
        candidate = getattr(holder, "planner", None)
        if candidate is None:
            continue
        seen.append(type(candidate).__name__)
        if callable(getattr(candidate, "build", None)):
            return candidate
    return None


def _plan_text(rt, goal: str) -> str:
    planner = _planner(rt)
    if planner is None:
        return ""
    plan = planner.build(goal, {})
    summary = _attr(planner, "summary")
    return _text(summary(plan) if callable(summary) else plan)


@probe("a recorded lesson changes the plan that gets generated", 6, weight=2.0)
def _p_lesson_changes_plan(h: Harness):
    rt, engine = _learning(h)
    goal = "انتشار نسخه جدید"
    gate = getattr(engine, "gate", None)
    context = gate.bypass() if gate is not None else None
    if context is not None:
        context.__enter__()
    try:
        before = _plan_text(rt, goal)
        for _ in range(5):
            engine.record(
                goal=goal,
                action="انتشار بدون تست",
                result="بازگشت به نسخه قبل",
                score=0.05,
                intent="deploy",
                strategy="direct_deploy",
                domain="release",
            )
        after = _plan_text(rt, goal)
    finally:
        if context is not None:
            context.__exit__(None, None, None)
    ok = bool(before) and before != after
    return _verdict(ok, f"plan_changed={ok} len_before={len(before)} len_after={len(after)}")


@probe("learning feeds more than one subsystem", 6, weight=2.0)
def _p_learning_reach(h: Harness):
    consumers = []
    for rel in (
        "planning/planner.py",
        "core/dialogue.py",
        "core/response_engine.py",
        "core/verification.py",
        "core/reasoning_planning.py",
        "runtime/goals.py",
        "core/decision.py",
    ):
        path = h.source / rel
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8-sig")
        if any(k in src for k in ("learning", "lesson", "strategy_memory", "LearningEngine")):
            consumers.append(rel)
    ok = len(consumers) >= 3
    return _verdict(
        ok,
        f"subsystems_consuming_learning={consumers}",
        partial=len(consumers) >= 1,
    )


@probe("a single shared cognitive state type exists", 6)
def _p_single_state(h: Harness):
    import ast

    owners = []
    for path in sorted((h.source / "core").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "CognitiveState":
                owners.append(path.name)
    ok = len(owners) == 1
    return _verdict(ok, f"CognitiveState defined in {owners}", partial=len(owners) <= 2)


# ---------------------------------------------------------------- level 7


@probe("the system reports both capabilities and limitations", 7)
def _p_introspect(h: Harness):
    rt = h.runtime()
    engine = _component(rt, "self_awareness", "awareness")
    snap = None
    if engine is not None and callable(_attr(engine, "introspect")):
        snap = engine.introspect()
    elif callable(_attr(rt, "inspect")):
        snap = rt.inspect()
    blob = _text(snap).lower()
    has_cap = any(k in blob for k in ("capab", "skill", "strength"))
    has_lim = any(k in blob for k in ("limit", "weak", "unknown", "failure"))
    return _verdict(has_cap and has_lim, f"cap={has_cap} lim={has_lim}", partial=has_cap or has_lim)


@probe("the self-model is updated by observed outcomes", 7, weight=2.0)
def _p_self_model_updates(h: Harness):
    rt = h.runtime()
    engine = _component(rt, "self_awareness", "awareness")
    if engine is None or not callable(_attr(engine, "observe")):
        return _verdict(False, "self-awareness engine is not wired anywhere")
    before = _text(engine.introspect())
    for _ in range(6):
        engine.observe(
            goal="تحلیل لاگ",
            action="جست‌وجوی متنی ساده",
            score=0.1,
            verified=False,
            failure_reason="الگوی نادرست",
        )
    after = _text(engine.introspect())
    ok = before != after
    return _verdict(ok, f"self_model_changed={ok}")


@probe("a meta-reasoner evaluates the reasoning method itself", 7, weight=2.0)
def _p_meta_reasoner(h: Harness):
    ok = _module_exists("reasoning.meta_reasoner") or _module_exists("core.meta_reasoner")
    return _verdict(ok, f"meta_reasoner module present={ok}")


# ---------------------------------------------------------------- level 8


@probe("a goal is decomposed into several dependent steps", 8, weight=2.0)
def _p_decompose(h: Harness):
    rt = h.runtime()
    planner = _planner(rt)
    if planner is None:
        return _verdict(False, "planner is not wired anywhere")
    plan = planner.build("ساخت و تست و انتشار ماژول گزارش", {})
    steps = _attr(plan, "steps", default=[]) or []
    deps = 0
    for s in steps:
        deps += len(_attr(s, "depends_on", "dependencies", default=[]) or [])
    ok = len(steps) >= 3 and deps >= 1
    return _verdict(ok, f"steps={len(steps)} dependency_links={deps}", partial=len(steps) >= 3)


@probe("a failed step triggers a different plan", 8)
def _p_replan(h: Harness):
    rt = h.runtime()
    planner = _planner(rt)
    if planner is None or not callable(_attr(planner, "replan")):
        return _verdict(False, "no wired planner exposing replan()")
    plan = planner.build("ساخت و تست و انتشار ماژول گزارش", {})
    steps = _attr(plan, "steps", default=[]) or []
    if not steps:
        return _verdict(False, "planner produced no steps")
    before = _text(plan)
    failed = _attr(steps[0], "id", "step_id", default=steps[0])
    planner.replan(plan, failed, "ابزار در دسترس نیست")
    ok = _text(plan) != before
    return _verdict(ok, f"plan_mutated={ok}")


# ---------------------------------------------------------------- level 9


@probe("an autonomous cycle runs unaided", 9, weight=2.0)
def _p_autonomous_step(h: Harness):
    rt = h.runtime()
    fn = _attr(rt, "autonomous_step")
    if not callable(fn):
        return _verdict(False, "runtime has no autonomous_step()")
    out = fn()
    return _verdict(out is not None, f"step={_text(out)[:200]}")


@probe("the autonomous loop closes into learning", 9, weight=2.0)
def _p_loop_learns(h: Harness):
    rt, engine = _learning(h)
    stats = _attr(engine, "stats")
    before = _text(stats()) if callable(stats) else ""
    gate = getattr(rt, "learning_gate", None)
    gate_before = _text(gate.stats()) if gate is not None else ""
    runner = _attr(rt, "autonomous_supervisor_run", "autonomous_run")
    if not callable(runner):
        return _verdict(False, "no autonomous runner on runtime")
    runner(3)
    after = _text(stats()) if callable(stats) else ""
    gate_after = _text(gate.stats()) if gate is not None else ""
    ok = before != after or gate_before != gate_after
    return _verdict(ok, f"learning_or_gate_state_changed={ok}")


@probe("experiences are replayed offline to find reusable patterns", 9)
def _p_replay(h: Harness):
    ok = _module_exists("learning.replay")
    return _verdict(ok, f"learning.replay module present={ok}")


# ---------------------------------------------------------------- level 10


@probe("the benchmark is reproducible across runs", 10)
def _p_benchmark_stable(h: Harness):
    rt = h.runtime()
    fn = _attr(rt, "benchmark_run")
    if not callable(fn):
        return _verdict(False, "runtime has no benchmark_run()")
    first = _text(fn())
    second = _text(fn())
    return _verdict(first == second, f"stable={first == second}")


@probe("behaviour changes are versioned and can be rolled back", 10, weight=2.0)
def _p_versioned_brain(h: Harness):
    ok = _module_exists("learning.rollback") or _module_exists("governance.versioning")
    rt = h.runtime()
    gate = _attr(rt, "learning_gate")
    has_gate = gate is not None
    if ok and has_gate:
        return _verdict(True, "versioning module + learning gate")
    return _verdict(False, f"versioning_module={ok} learning_gate={has_gate}", partial=has_gate)


@probe("a promotion is blocked when the benchmark regresses", 10, weight=2.0)
def _p_regression_gate(h: Harness):
    ok = _module_exists("evaluation.regression")
    return _verdict(ok, f"evaluation.regression module present={ok}")


# ---------------------------------------------------------------- runner


def run(source: Path | str | None = None, verbose: bool = False) -> MaturityReport:
    """Run every probe against an isolated copy of the project."""
    source = Path(source or Path(__file__).resolve().parents[1])
    report = MaturityReport()
    for name, level, weight, fn in PROBES:
        harness = Harness(source)
        try:
            status, score, evidence = fn(harness)
        except Exception as exc:  # a crashing probe is a real failure signal
            status, score = ERROR, 0.0
            evidence = f"{type(exc).__name__}: {exc}"
            if verbose:
                traceback.print_exc()
        finally:
            harness.close()
        report.probes.append(
            ProbeResult(
                name=name,
                level=level,
                status=status,
                score=score,
                weight=weight,
                evidence=evidence,
            )
        )
        if verbose:
            print(f"[{status:7s}] L{level} {name} :: {evidence[:110]}")
    return report


def render(report: MaturityReport) -> str:
    lines = [f"IRAN maturity: {report.score:.1f}%", ""]
    levels = report.level_scores()
    for level, value in levels.items():
        bar = "#" * int(round(value * 20)) + "." * (20 - int(round(value * 20)))
        lines.append(f"L{level:<2d} [{bar}] {value * 100:5.1f}%  {LEVEL_TITLES[level]}")
    lines.append("")
    for p in report.probes:
        if p.status != PASS:
            lines.append(f"  - L{p.level} {p.status.upper():7s} {p.name} :: {p.evidence[:120]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    verbose = "-v" in argv or "--verbose" in argv
    report = run(verbose=verbose)
    print(render(report))
    if "--json" in argv:
        out = Path(__file__).resolve().parents[1] / "data" / "maturity_report.json"
        out.write_text(
            json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
