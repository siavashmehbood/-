import json
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class CognitiveBrainContractTests(unittest.TestCase):
    def make_runtime(self):
        root = Path(tempfile.mkdtemp())
        cfg = json.loads(Path("config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"] = "data/test.db"
        cfg["runtime"]["event_log"] = "data/events.jsonl"
        cfg["runtime"]["goals"] = "data/goals.json"
        (root / "data").mkdir()
        (root / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return IranRuntime(root)

    def test_all_user_input_enters_one_cognitive_boundary(self):
        runtime = self.make_runtime()
        try:
            self.assertTrue(runtime.handle("سلام"))
            command_result = runtime.handle("/learning-status")
            self.assertTrue(command_result)
            self.assertEqual(runtime.cognitive_system.last_answer, command_result)
        finally:
            runtime.close()

    def test_learning_guidance_is_capability_neutral(self):
        runtime = self.make_runtime()
        try:
            guidance = runtime.cognitive_system.guidance("یک مسئله آزمایشی", "task", "task")
            self.assertIsInstance(guidance, dict)
            self.assertIn("failure_signal", guidance)
        finally:
            runtime.close()

    def test_brain_exposes_integrated_components(self):
        runtime = self.make_runtime()
        try:
            components = runtime.cognitive_system.inspect()
            for key in ("memory", "knowledge", "learning", "reasoning",
                        "semantic_verification", "autonomy", "self_improvement",
                        "self_directed_learning"):
                self.assertIn(key, components)
        finally:
            runtime.close()
