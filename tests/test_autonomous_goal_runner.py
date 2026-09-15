import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class AutonomousGoalRunnerTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / "config.json"
        config = json.loads(source.read_text(encoding="utf-8-sig"))
        config["memory"]["db"] = "data/m.db"
        config["runtime"]["event_log"] = "data/e.jsonl"
        config["runtime"]["goals"] = "data/g.json"
        config["runtime"]["autonomous_goal_state"] = "data/a.json"
        root = Path(directory)
        (root / "data").mkdir(exist_ok=True)
        (root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return IranRuntime(root)

    def test_goal_progresses_across_cycles(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                goal = runtime.goals.add("multi stage autonomous goal")
                reports = runtime.autonomous_supervisor_run(5)
                progress = [r["long_horizon"]["step"] for r in reports]
                self.assertEqual(progress, [1, 2, 3, 4, 5])
                stored = next(x for x in runtime.goals.list() if x["id"] == goal["id"])
                self.assertEqual(stored["status"], "completed")
            finally:
                runtime.close()

    def test_progress_state_is_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            goal = runtime.goals.add("persistent autonomous goal")
            first = runtime.autonomous_supervisor_step()
            self.assertEqual(first["long_horizon"]["step"], 1)
            snapshot = runtime.autonomous_supervisor.goal_progress_snapshot()
            self.assertEqual(snapshot[str(goal["id"])]["step"], 1)
            runtime.close()

            runtime2 = self.make_runtime(directory)
            try:
                snapshot2 = runtime2.autonomous_supervisor.goal_progress_snapshot()
                self.assertEqual(snapshot2[str(goal["id"])]["step"], 1)
            finally:
                runtime2.close()


if __name__ == "__main__":
    unittest.main()

