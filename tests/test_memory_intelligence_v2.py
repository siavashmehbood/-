import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from memory.store import Memory
from core.dialogue import ConversationState
from core.memory_intelligence import MemoryIntelligence


class MemoryIntelligenceV2Tests(unittest.TestCase):
    def test_relevance_beats_recent_irrelevant_memory(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            m.add("user", "بحث معماری حافظه و بازیابی تجربه", .9, .9, "test")
            m.add("user", "امروز درباره رنگ رابط کاربری صحبت کردیم", .9, .9, "test")
            out = MemoryIntelligence(m).retrieve("درباره حافظه چی گفتیم", limit=2)
            self.assertTrue(out)
            self.assertIn("حافظه", out[0].content)
            m.close()

    def test_rejected_answer_is_not_selected(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            bad = "پاسخ قدیمی و اشتباه"
            m.add("assistant", bad, .95, .95, "test")
            state = ConversationState()
            state.reject(bad)
            out = MemoryIntelligence(m).retrieve("پاسخ قدیمی و اشتباه", state, limit=5)
            self.assertFalse(any(x.content == bad for x in out))
            m.close()

    def test_accepted_answer_gets_outcome_priority(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            text = "پایتون برای پروژه مناسب است"
            m.add("assistant", text, .55, .55, "test")
            state = ConversationState()
            state.accept(text)
            out = MemoryIntelligence(m).retrieve("پایتون پروژه", state, limit=5)
            self.assertTrue(out)
            self.assertEqual(out[0].status, "accepted")
            m.close()

    def test_old_memory_loses_freshness(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            old = (datetime.now() - timedelta(days=180)).isoformat(timespec="seconds")
            new = datetime.now().isoformat(timespec="seconds")
            m.conn.execute(
                "INSERT INTO memories(kind,content,importance,created_at,confidence,source) VALUES(?,?,?,?,?,?)",
                ("user", "بحث حافظه قدیمی", .8, old, .8, "test"),
            )
            m.conn.execute(
                "INSERT INTO memories(kind,content,importance,created_at,confidence,source) VALUES(?,?,?,?,?,?)",
                ("user", "بحث حافظه جدید", .8, new, .8, "test"),
            )
            m.conn.commit()
            out = MemoryIntelligence(m).retrieve("بحث حافظه", limit=2)
            self.assertEqual(out[0].content, "بحث حافظه جدید")
            m.close()

    def test_context_contains_explainable_trace(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.db")
            m.add("user", "معماری شناختی و حافظه", .8, .9, "test")
            context = MemoryIntelligence(m).build_context("حافظه معماری", limit=3)
            self.assertIn("candidates", context)
            self.assertIn("selected", context)
            self.assertTrue(context["candidates"][0]["reason"])
            m.close()


if __name__ == "__main__":
    unittest.main()
