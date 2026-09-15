import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from core.autonomous_supervisor import AutonomousBenchmark


class AutonomousSupervisorTests(unittest.TestCase):
    def make_runtime(self, directory):
        source = Path(__file__).resolve().parents[1] / "config.json"
        config = json.loads(source.read_text(encoding="utf-8-sig"))
        config["memory"]["db"] = "data/m.db"
        config["runtime"]["event_log"] = "data/e.jsonl"
        config["runtime"]["goals"] = "data/g.json"
        root = Path(directory)
        (root / "data").mkdir()
        (root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return IranRuntime(root)

    def test_initial_cycle_is_safe_and_observable(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                report = runtime.autonomous_supervisor_step()
                self.assertEqual(report["decision"]["permission"], "read")
                self.assertTrue(report["decision"]["safe"])
                self.assertTrue(report["verified"])
                self.assertTrue(any(e["event"] == "supervisor_cycle" for e in runtime.events.recent(20)))
            finally:
                runtime.close()

    def test_change_detection_creates_initiative(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                runtime.autonomous_supervisor_step()
                target = Path(directory) / "data" / "watched.txt"
                target.write_text("change", encoding="utf-8")
                report = runtime.autonomous_supervisor_step()
                self.assertTrue(any(s["kind"] == "files_added" for s in report["signals"]))
                self.assertIn(report["decision"]["action"], {"project_summary", "project_files"})
            finally:
                runtime.close()

    def test_benchmark_has_100_scenarios(self):
        result = AutonomousBenchmark().run()
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["passed"], 100)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()

