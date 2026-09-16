"""Symbolic decision cycle: perceive -> match -> select -> act -> verify."""
from dataclasses import dataclass, field
from .goal_stack import GoalStack
from .production_rules import ProductionSystem


@dataclass
class CycleResult:
    cycle: int
    goal: str | None
    matched_rules: list[dict] = field(default_factory=list)
    selected_action: str | None = None
    status: str = "idle"
    trace: list[str] = field(default_factory=list)


class DecisionCycle:
    """Small deterministic executive loop suitable for offline symbolic cognition."""

    def __init__(self, rules=None, goals=None, max_cycles=32):
        self.rules = rules or ProductionSystem()
        self.goals = goals or GoalStack()
        self.max_cycles = int(max_cycles)
        self.cycle = 0
        self.halted = False
        self.trace = []

    def reset(self):
        self.cycle = 0
        self.halted = False
        self.trace.clear()

    def step(self, facts, result=None):
        if self.halted or self.cycle >= self.max_cycles:
            return CycleResult(self.cycle, self.goals.current().name if self.goals.current() else None,
                               status="halted", trace=list(self.trace[-12:]))
        self.cycle += 1
        goal = self.goals.current()
        matches = self.rules.match(facts)
        fired = self.rules.fire(facts, 1)
        action = fired[0]["action"] if fired else None
        if action:
            self.trace.append(f"cycle={self.cycle} select={action}")
            status = "action_selected"
        elif goal:
            self.trace.append(f"cycle={self.cycle} no_rule goal={goal.name}")
            status = "awaiting_evidence"
        else:
            self.trace.append(f"cycle={self.cycle} idle")
            status = "idle"
        if result is not None and goal:
            self.goals.advance(result)
            if not self.goals.current():
                self.halted = True
                status = "goal_complete"
        return CycleResult(self.cycle, goal.name if goal else None,
                           fired, action, status, list(self.trace[-12:]))

    def run(self, facts, max_steps=None, results=None):
        limit = min(self.max_cycles, int(max_steps or self.max_cycles))
        outputs = []
        for index in range(limit):
            result = results[index] if results and index < len(results) else None
            out = self.step(facts, result)
            outputs.append(out)
            if out.status in {"goal_complete", "halted"}:
                break
            if out.status == "idle" and not self.goals.current():
                break
        return outputs

    def snapshot(self):
        return {"cycle": self.cycle, "halted": self.halted,
                "goals": self.goals.snapshot(), "rules": self.rules.snapshot(),
                "trace": list(self.trace)}
