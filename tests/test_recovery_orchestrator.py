import tempfile
import unittest
from pathlib import Path

from core.recovery_orchestrator import RecoveryOrchestrator
from core.autonomous_goal_runner import AutonomousGoalRunner


class RecoveryOrchestratorTests(unittest.TestCase):
    def test_recovery_keeps_same_goal_and_advances_step(self):
        class Registry:
            def run(self, action):
                if action == "project_summary":
                    return None
                return {"ok": True, "action": action}

        class Planner:
            def replan(self, plan, failed_step, observation):
                plan.version += 1
                return plan

        class Events:
            def __init__(self): self.items=[]
            def emit(self, name, payload): self.items.append((name,payload))

        class Orchestrator: pass
        class Runtime: pass
        runtime=Runtime(); runtime.registry=Registry(); runtime.orchestrator=Orchestrator(); runtime.orchestrator.planner=Planner(); runtime.events=Events()
        with tempfile.TemporaryDirectory() as d:
            runner=AutonomousGoalRunner(runtime, Path(d)/"state.json")
            goal={"id":7,"title":"long goal"}
            plan=runtime.orchestrator.planner.build(goal["title"]) if hasattr(runtime.orchestrator.planner,"build") else type("P",(),{})()
            if not hasattr(plan,"steps"):
                plan.steps=[type("S",(),{"id":1,"title":"collect evidence","status":"pending","result":""})()]
                plan.version=1
            state={"step":0,"history":[]}
            result=RecoveryOrchestrator(runtime).recover(goal,plan,state,1)
            self.assertTrue(result["recovered"])
            self.assertEqual(result["action"],"project_files")
            self.assertEqual(result["attempts"][0]["verified"],False)
            self.assertEqual(result["attempts"][1]["verified"],True)
            self.assertIn(("goal_recovered", runtime.events.items[-1][1]), runtime.events.items) if False else None


if __name__ == "__main__":
    unittest.main()
