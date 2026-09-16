import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class CognitivePipelineTests(unittest.TestCase):
    def make_runtime(self):
        root = Path(tempfile.mkdtemp(prefix="iran_pipeline_"))
        shutil.copy("config.json", root / "config.json")
        (root / "data").mkdir(exist_ok=True)
        config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
        config["memory"]["db"] = "data/pipeline.db"
        config["runtime"]["event_log"] = "data/pipeline.jsonl"
        config["runtime"]["goals"] = "data/goals.json"
        (root / "config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        return root, IranRuntime(root)

    def tearDown_runtime(self, root, runtime):
        runtime.close()
        shutil.rmtree(root, ignore_errors=True)

    def test_single_pipeline_object_is_used(self):
        root, runtime = self.make_runtime()
        try:
            runtime.handle("پایتون چیه؟")
            self.assertTrue(getattr(runtime.dialogue, "cognitive_pipeline", None))
            self.assertTrue(runtime.dialogue._canonical_pipeline)
        finally:
            self.tearDown_runtime(root, runtime)

    def test_pipeline_trace_contains_reasoning_and_verification(self):
        root, runtime = self.make_runtime()
        try:
            runtime.handle("پایتخت ایران کجاست؟")
            trace = runtime.conversation_trace()[-1]
            self.assertEqual(trace["reasoning_status"], "VERIFIED_CANDIDATE")
            self.assertEqual(trace["verification_status"], "PASS")
        finally:
            self.tearDown_runtime(root, runtime)

    def test_user_identity_and_work_correction_are_memory_grounded(self):
        root, runtime = self.make_runtime()
        try:
            self.assertIn("سیاوش", runtime.handle("من سیاوش هستم."))
            self.assertIn("سیاوش", runtime.handle("اسم من چیه؟"))
            runtime.handle("من روی پایتون کار می‌کنم.")
            self.assertIn("پایتون", runtime.handle("موضوع کارم چی بود؟"))
            runtime.handle("نه، منظورم Django بود.")
            self.assertIn("Django", runtime.handle("پس الان روی چی کار می‌کنم؟"))
            facts = runtime.user_model.current_belief("work_on", limit=1)
            self.assertEqual(facts[0]["object"], "Django")
        finally:
            self.tearDown_runtime(root, runtime)

    def test_unknown_remains_explicit(self):
        root, runtime = self.make_runtime()
        try:
            answer = runtime.handle("دمای دقیق هسته مشتری در سال ۱۴۲۰ چقدر است؟")
            self.assertTrue(answer.startswith("UNKNOWN:"))
        finally:
            self.tearDown_runtime(root, runtime)
