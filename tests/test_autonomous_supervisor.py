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
                self.assertTrue(report["curriculum_learning"]["ok"])
                self.assertIn("created", report["curriculum_learning"])
                self.assertIn("review_queue", report["curriculum_learning"])
                self.assertIn("pending", report["curriculum_learning"]["review_queue"])
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

    def test_supervisor_uses_canonical_class_methods(self):
        # Regression guard for the legacy monkey-patch cleanup: core supervisor
        # behavior must live on the class instead of being replaced after class
        # creation by module-level versioned functions.
        from core.autonomous_supervisor import AutonomousSupervisor
        self.assertEqual(AutonomousSupervisor.step.__qualname__, "AutonomousSupervisor.step")
        self.assertEqual(AutonomousSupervisor.__init__.__qualname__, "AutonomousSupervisor.__init__")
        self.assertEqual(AutonomousSupervisor._choose_action.__qualname__, "AutonomousSupervisor._choose_action")

    def test_supervisor_source_has_no_runtime_method_rebinding(self):
        from pathlib import Path
        import core.autonomous_supervisor as supervisor_module

        source = Path(supervisor_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("AutonomousSupervisor.step =", source)
        self.assertNotIn("AutonomousSupervisor.__init__ =", source)
        self.assertNotIn("AutonomousSupervisor._choose_action =", source)

    def test_routine_cycle_does_not_record_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                calls = []
                original = runtime.learning.record
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs))
                report = runtime.autonomous_supervisor_step()
                autonomous_calls = [call for call in calls if (len(call[0]) > 4 and call[0][4] == "autonomous") or call[1].get("intent") == "autonomous"]
                self.assertEqual(autonomous_calls, [])
                self.assertFalse(report["learning"]["recorded"])
            finally:
                runtime.learning.record = original
                runtime.close()

    def test_purposeful_learning_gate_requires_effect_and_records_once(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                supervisor = runtime.autonomous_supervisor
                supervisor.monitor._last_manifest = supervisor.monitor.manifest()
                target = Path(directory) / "novel.txt"
                target.write_text("novel", encoding="utf-8")
                calls = []
                original_record = runtime.learning.record
                original_choose = supervisor._choose_action
                supervisor._choose_action = lambda selected: "project_files"
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs)) or {"pending_approval": True}
                original_run = runtime.registry.run
                runtime.registry.run = lambda action: {"novel": True}
                original_lessons = runtime.learning.lessons
                runtime.learning.lessons = lambda objective, limit: []
                # Expected effect is deliberately absent: novel observation alone must not learn.
                report = runtime.autonomous_supervisor_step()
                autonomous = [x for x in calls if x[1].get("intent") == "autonomous"]
                self.assertEqual(autonomous, [])
                self.assertFalse(report["learning"]["purposeful"])
            finally:
                runtime.learning.record = original_record
                runtime.learning.lessons = original_lessons
                runtime.registry.run = original_run
                supervisor._choose_action = original_choose
                runtime.close()

    def test_repeated_purposeful_observation_is_not_recorded_again(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            supervisor = runtime.autonomous_supervisor
            original_record, original_lessons = runtime.learning.record, runtime.learning.lessons
            original_run, original_observe = runtime.registry.run, supervisor.monitor.observe_changes
            original_choose, original_control = supervisor._choose_action, supervisor.self_awareness.control_next_action
            try:
                from core.autonomous_supervisor import EnvironmentSignal
                calls = []
                supervisor.monitor.observe_changes = lambda: [EnvironmentSignal("files_changed", ["same.txt"], novelty=1.0)]
                supervisor._choose_action = lambda selected: "project_files"
                runtime.registry.run = lambda action: {"changed": ["same.txt"]}
                result_text = json.dumps({"changed": ["same.txt"]}, ensure_ascii=False, sort_keys=True, default=str)[:1200]
                runtime.learning.lessons = lambda objective, limit: [{"action": "project_files", "result": result_text}]
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs))
                supervisor.self_awareness.control_next_action = lambda candidates: {"preferred_action": "project_files", "reason": "known", "expected_effect": "understand project change"}
                report = runtime.autonomous_supervisor_step()
                self.assertEqual([x for x in calls if x[1].get("intent") == "autonomous"], [])
                self.assertFalse(report["learning"]["purposeful"])
            finally:
                runtime.learning.record, runtime.learning.lessons = original_record, original_lessons
                runtime.registry.run, supervisor.monitor.observe_changes = original_run, original_observe
                supervisor._choose_action, supervisor.self_awareness.control_next_action = original_choose, original_control
                runtime.close()

    def test_low_novelty_never_records_autonomous_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            supervisor = runtime.autonomous_supervisor
            original_record, original_lessons = runtime.learning.record, runtime.learning.lessons
            original_run, original_observe = runtime.registry.run, supervisor.monitor.observe_changes
            original_control = supervisor.self_awareness.control_next_action
            try:
                from core.autonomous_supervisor import EnvironmentSignal
                calls = []
                supervisor.monitor.observe_changes = lambda: [EnvironmentSignal("baseline", {"files": 1}, novelty=.2)]
                runtime.registry.run = lambda action: {"ok": True}
                runtime.learning.lessons = lambda objective, limit: []
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs))
                supervisor.self_awareness.control_next_action = lambda candidates: {"preferred_action": "project_summary", "reason": "stable", "expected_effect": "maintain awareness"}
                report = runtime.autonomous_supervisor_step()
                self.assertEqual([x for x in calls if x[1].get("intent") == "autonomous"], [])
                self.assertFalse(report["learning"]["purposeful"])
            finally:
                runtime.learning.record, runtime.learning.lessons = original_record, original_lessons
                runtime.registry.run, supervisor.monitor.observe_changes = original_run, original_observe
                supervisor.self_awareness.control_next_action = original_control
                runtime.close()

    def test_unverified_observation_never_records_autonomous_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            supervisor = runtime.autonomous_supervisor
            original_record, original_lessons = runtime.learning.record, runtime.learning.lessons
            original_run, original_observe = runtime.registry.run, supervisor.monitor.observe_changes
            original_control = supervisor.self_awareness.control_next_action
            try:
                from core.autonomous_supervisor import EnvironmentSignal
                calls = []
                supervisor.monitor.observe_changes = lambda: [EnvironmentSignal("files_changed", ["x"], novelty=1.0)]
                runtime.registry.run = lambda action: None
                runtime.learning.lessons = lambda objective, limit: []
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs))
                supervisor.self_awareness.control_next_action = lambda candidates: {"preferred_action": "project_files", "reason": "novel", "expected_effect": "understand change"}
                report = runtime.autonomous_supervisor_step()
                self.assertFalse(report["verified"])
                self.assertEqual([x for x in calls if x[1].get("intent") == "autonomous"], [])
                self.assertFalse(report["learning"]["purposeful"])
            finally:
                runtime.learning.record, runtime.learning.lessons = original_record, original_lessons
                runtime.registry.run, supervisor.monitor.observe_changes = original_run, original_observe
                supervisor.self_awareness.control_next_action = original_control
                runtime.close()

    def test_curriculum_generation_runs_once_per_supervisor_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                calls = []
                original = runtime.generate_curriculum_learning_inputs
                runtime.generate_curriculum_learning_inputs = lambda count: calls.append(count) or {"ok": True, "created": 0, "review_queue": {"pending": 0}}
                runtime.autonomous_supervisor_step()
                self.assertEqual(calls, [24])
            finally:
                runtime.generate_curriculum_learning_inputs = original
                runtime.close()

    def test_purposeful_gate_records_exactly_one_autonomous_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            supervisor = runtime.autonomous_supervisor
            original_record = runtime.learning.record
            original_lessons = runtime.learning.lessons
            original_run = runtime.registry.run
            original_observe = supervisor.monitor.observe_changes
            original_choose = supervisor._choose_action
            original_control = supervisor.self_awareness.control_next_action
            try:
                from core.autonomous_supervisor import EnvironmentSignal
                calls = []
                supervisor.monitor.observe_changes = lambda: [EnvironmentSignal("files_changed", ["novel.txt"], novelty=1.0)]
                supervisor._choose_action = lambda selected: "project_files"
                runtime.registry.run = lambda action: {"changed": ["novel.txt"]}
                runtime.learning.lessons = lambda objective, limit: []
                runtime.learning.record = lambda *args, **kwargs: calls.append((args, kwargs)) or {"pending_approval": True}
                supervisor.self_awareness.control_next_action = lambda candidates: {"preferred_action": "project_files", "reason": "novel evidence", "expected_effect": "understand project change"}
                report = runtime.autonomous_supervisor_step()
                autonomous = [x for x in calls if x[1].get("intent") == "autonomous"]
                self.assertEqual(len(autonomous), 1)
                self.assertTrue(report["learning"]["purposeful"])
                self.assertTrue(report["learning"]["pending_approval"])
                self.assertEqual(report["decision"]["expected_effect"], "understand project change")
            finally:
                runtime.learning.record = original_record
                runtime.learning.lessons = original_lessons
                runtime.registry.run = original_run
                supervisor.monitor.observe_changes = original_observe
                supervisor._choose_action = original_choose
                supervisor.self_awareness.control_next_action = original_control
                runtime.close()


    def test_curriculum_creation_metrics_distinguish_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.make_runtime(directory)
            try:
                first = runtime.generate_curriculum_learning_inputs(4)
                second = runtime.generate_curriculum_learning_inputs(4)
                self.assertEqual(first["created"], 4)
                self.assertEqual(first["reused"], 0)
                self.assertEqual(second["created"], 0)
                self.assertEqual(second["reused"], 4)
                self.assertEqual([g["goal_id"] for g in first["goals"]], [g["goal_id"] for g in second["goals"]])
            finally:
                runtime.close()

    def test_benchmark_has_100_scenarios(self):
        result = AutonomousBenchmark().run()
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["passed"], 100)
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()

