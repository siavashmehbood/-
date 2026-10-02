"""Regression coverage for structured conversation fact memory.

The public runtime path must resolve explicit user-owned entity facts before
falling back to raw conversation-history similarity.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime

SRC = Path(__file__).resolve().parents[1]


class ConversationFactMemoryRegression(unittest.TestCase):
    def runtime(self):
        root = Path(tempfile.mkdtemp(prefix="iran_fact_memory_"))
        shutil.copy(SRC / "config.json", root / "config.json")
        shutil.copytree(SRC / "data", root / "data")
        (root / "logs").mkdir(exist_ok=True)
        for name in ("conversation_state.json", "conversation_events.json"):
            (root / "data" / name).unlink(missing_ok=True)
        cfg = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"] = "data/test.db"
        cfg["runtime"]["event_log"] = "logs/events.jsonl"
        cfg["runtime"]["goals"] = "data/goals.json"
        (root / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        return IranRuntime(root)

    def assert_value_answer(self, answer, value):
        self.assertIn(value, answer)
        self.assertNotIn("اسم پروژه من چیه", answer)
        self.assertNotIn("اسم پروژه‌ام چیست", answer)

    def test_project_name_fact_survives_context_switch_and_restart(self):
        r = self.runtime()
        root = r.root
        try:
            r.handle("سلام")
            r.handle("اسم من سیاوش محبودی است، یادت بماند.")
            self.assertIn("سیاوش", r.handle("اسم من چیه؟"))

            r.handle("من یک پروژه برای کتاب و کتاب صوتی دارم.")
            r.handle("اسم پروژه من داناست، یادت بماند.")
            self.assert_value_answer(r.handle("اسم پروژه من چیه؟"), "دانا")
            self.assert_value_answer(r.handle("من چند لحظه پیش گفتم اسم پروژه‌ام چیست؟"), "دانا")

            r.handle("حالا درباره ویندوز حرف بزنیم.")
            self.assert_value_answer(r.handle("برگردیم به پروژه قبلی؛ اسمش چی بود؟"), "دانا")
        finally:
            r.close()

        r2 = IranRuntime(root)
        try:
            self.assert_value_answer(r2.handle("اسم پروژه من چی بود؟"), "دانا")
            fs = r2.cognitive_system.pipeline.conversation_foundation.current_state()
            self.assertEqual(fs.get("slots", {}).get("user.project_name"), "دانا")
            self.assertEqual(r2.cognitive_system.architecture_contract()["decision_owner"], "CognitiveSystem")
        finally:
            r2.close()

    def test_current_turn_fact_and_generic_owned_entity_name(self):
        r = self.runtime()
        try:
            a = r.handle("من گفتم اسم پروژه‌ام داناست. حالا اسم پروژه‌ام چیست؟")
            self.assert_value_answer(a, "دانا")

            r.handle("اسم شرکت من آریاست.")
            b = r.handle("اسم شرکتم چی بود؟")
            self.assertIn("آریا", b)
            self.assertNotIn("اسم شرکتم چی بود", b)
        finally:
            r.close()


if __name__ == "__main__":
    unittest.main()
