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

    def test_final_supervisor_contract_covers_composed_layers(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                report = runtime.autonomous_supervisor_step()
                # Freeze the externally observable contract before removing the
                # historical step/init monkey-patch chain.
                for key in (
                    "cycle", "signals", "initiatives", "selected", "reasoning",
                    "decision", "observation", "verified", "reflection",
                    "autonomy_status", "decision_explanation", "stagnation",
                    "plan", "long_horizon", "self_awareness",
                    "self_awareness_control", "curriculum_learning", "learning",
                ):
                    self.assertIn(key, report)
                self.assertEqual(report["decision"]["permission"], "read")
                self.assertTrue(report["decision"]["safe"])
                self.assertIn(
                    report["decision"]["action"],
                    {"project_summary", "project_files", "memory_search"},
                )
                self.assertIn(report["plan"]["status"], {"active", "ready", "idle", "unavailable", "completed", "pending"})
                self.assertIn("status", report["long_horizon"])
                self.assertIn("recorded", report["learning"])
                self.assertFalse(report["learning"]["recorded"])
                self.assertIn("pending", report["curriculum_learning"])
                events = {e["event"] for e in runtime.events.recent(100)}
                self.assertIn("supervisor_cycle", events)
                self.assertIn("self_awareness_updated", events)
                self.assertIn("self_awareness_control", events)
            finally:
                runtime.close()

    def test_repeated_monitor_cycles_surface_stagnation_without_write_permission(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                reports = [runtime.autonomous_supervisor_step() for _ in range(5)]
                self.assertTrue(any(r["stagnation"]["detected"] for r in reports))
                self.assertTrue(all(r["decision"]["permission"] == "read" for r in reports))
                self.assertTrue(all(r["decision"]["safe"] for r in reports))
            finally:
                runtime.close()

    def test_benchmark_has_100_scenarios(self):
        result = AutonomousBenchmark().run()
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["passed"], 100)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()

