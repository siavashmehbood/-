import unittest

from core.production_rules import ProductionSystem
from core.goal_stack import GoalStack
from core.decision_cycle import DecisionCycle


class TestExecutiveArchitecture(unittest.TestCase):
    def test_production_rule_priority_and_binding(self):
        system = ProductionSystem()
        system.add("inspect", ["state=uncertain", "target={target}"],
                   "inspect {target}", priority=1)
        system.add("fallback", ["state=uncertain"], "ask", priority=0)
        fired = system.fire(["state=uncertain", "target=project"], 1)
        self.assertEqual(fired[0]["rule"], "inspect")
        self.assertEqual(fired[0]["action"], "inspect project")

    def test_goal_stack_subgoal_lifecycle(self):
        goals = GoalStack(max_depth=3)
        root = goals.push("learn", steps=["retrieve", "verify"])
        goals.push("retrieve", parent=root.name)
        self.assertEqual(goals.current().name, "retrieve")
        goals.pop("evidence ready")
        self.assertEqual(goals.current().name, "learn")
        goals.advance("verified")
        goals.advance("completed")
        self.assertIsNone(goals.current())

    def test_decision_cycle_selects_rule_and_completes_goal(self):
        system = ProductionSystem()
        system.add("act", ["ready"], "execute", priority=2)
        goals = GoalStack()
        cycle = DecisionCycle(system, goals)
        goals.push("task", steps=["execute"])
        first = cycle.step(["ready"])
        self.assertEqual(first.selected_action, "execute")
        second = cycle.step(["ready"], result="done")
        self.assertEqual(second.status, "goal_complete")
        self.assertTrue(cycle.halted)


if __name__ == "__main__":
    unittest.main()
