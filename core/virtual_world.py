from dataclasses import dataclass, field
from typing import Callable


@dataclass
class WorldEvent:
    name: str
    target: str
    value: object


@dataclass
class VirtualWorld:
    """Deterministic sandbox for long-horizon cognitive evaluation."""
    state: dict = field(default_factory=lambda: {
        "system": "healthy", "queue": 2, "resource": 5, "risk": 0.1
    })
    events: list[WorldEvent] = field(default_factory=list)

    def observe(self) -> dict:
        return dict(self.state)

    def apply(self, event: WorldEvent):
        if event.name == "set":
            self.state[event.target] = event.value
        elif event.name == "increment":
            self.state[event.target] = self.state.get(event.target, 0) + event.value
        self.events.append(event)

    def goal_satisfied(self, goal: str) -> bool:
        if goal == "restore system":
            return self.state.get("system") == "healthy"
        if goal == "reduce queue":
            return self.state.get("queue", 0) <= 0
        return False

    def legal_actions(self) -> list[str]:
        actions = ["inspect"]
        if self.state.get("system") != "healthy":
            actions.append("restore")
        if self.state.get("queue", 0) > 0 and self.state.get("resource", 0) > 0:
            actions.append("process_queue")
        return actions

    def act(self, action: str) -> dict:
        before = self.observe()
        if action == "inspect":
            return {"action": action, "success": True, "before": before, "after": before}
        if action == "restore" and self.state.get("resource", 0) >= 1:
            self.apply(WorldEvent("set", "system", "healthy"))
            self.apply(WorldEvent("increment", "resource", -1))
        elif action == "process_queue" and self.state.get("queue", 0) > 0:
            self.apply(WorldEvent("increment", "queue", -1))
            self.apply(WorldEvent("increment", "resource", -1))
        else:
            return {"action": action, "success": False, "before": before, "after": self.observe()}
        after = self.observe()
        return {"action": action, "success": True, "before": before, "after": after}


class VirtualWorldBenchmark:
    def run(self, cycles: int = 50, world_factory: Callable[[], VirtualWorld] = VirtualWorld):
        world = world_factory()
        history = []
        goal = "restore system"
        world.apply(WorldEvent("set", "system", "degraded"))
        for cycle in range(max(1, cycles)):
            observation = world.observe()
            actions = world.legal_actions()
            action = "restore" if "restore" in actions else "inspect"
            result = world.act(action)
            history.append({"cycle": cycle + 1, "observation": observation, "result": result})
            if world.goal_satisfied(goal):
                return {"success": True, "cycles": cycle + 1, "goal": goal, "history": history}
        return {"success": world.goal_satisfied(goal), "cycles": cycles, "goal": goal, "history": history}
