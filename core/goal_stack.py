"""Bounded symbolic goal/subgoal stack for the IRAN executive cycle."""
from dataclasses import dataclass, field


@dataclass
class Goal:
    name: str
    parent: str | None = None
    status: str = "pending"
    priority: int = 0
    steps: list[str] = field(default_factory=list)
    current_step: int = 0
    result: str | None = None

    @property
    def complete(self):
        return self.status == "done"


class GoalStack:
    """LIFO subgoal stack with explicit completion and bounded depth."""

    def __init__(self, max_depth=16):
        self.max_depth = int(max_depth)
        self._stack = []

    def push(self, name, parent=None, priority=0, steps=None):
        if len(self._stack) >= self.max_depth:
            raise OverflowError("goal stack depth exceeded")
        goal = Goal(str(name), parent, "active", int(priority), list(steps or []))
        self._stack.append(goal)
        return goal

    def current(self):
        return self._stack[-1] if self._stack else None

    def pop(self, result=None):
        if not self._stack:
            return None
        goal = self._stack.pop()
        goal.status = "done"
        goal.result = None if result is None else str(result)
        return goal

    def advance(self, result=None):
        goal = self.current()
        if goal is None:
            return None
        goal.result = None if result is None else str(result)
        if goal.current_step + 1 >= len(goal.steps):
            return self.pop(result)
        goal.current_step += 1
        return goal

    def pause(self):
        if self.current():
            self.current().status = "paused"

    def resume(self):
        if self.current():
            self.current().status = "active"

    def snapshot(self):
        return [goal.__dict__.copy() for goal in self._stack]

    def clear(self):
        self._stack.clear()
