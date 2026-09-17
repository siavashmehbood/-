import unittest
from core.context_tracker import ContextTracker


class ContextTrackerV2Tests(unittest.TestCase):
    def test_topic_hierarchy(self):
        t = ContextTracker()
        t.observe("x", {"entities": [{"text": "Django", "parent": "Python"}]})
        self.assertEqual(t.active_topic, "Django")
        row = next(x for x in t.snapshot().topics if x["value"] == "Django")
        self.assertEqual(row["parent"], "Python")

    def test_previous_topic_survives_switch(self):
        t = ContextTracker()
        t.observe("x", {"entities": [{"text": "Python"}]})
        t.observe("y", {"entities": [{"text": "Django"}]})
        self.assertEqual(t.resolve(), "Django")
        self.assertEqual(t.previous_topic(), "Python")

    def test_slot_conflict_is_recorded(self):
        t = ContextTracker()
        t.observe("x", {"slots": {"language": "Python"}})
        t.observe("y", {"slots": {"language": "Django"}})
        self.assertEqual(t.slots["language"], "Django")
        self.assertEqual(t.conflicts[-1]["old"], "Python")
        self.assertEqual(t.conflicts[-1]["new"], "Django")

    def test_persistence_keeps_new_context(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "context.json"
            t = ContextTracker()
            t.observe("x", {"entities": [{"text": "IRAN"}]})
            t.observe("y", {"slots": {"mode": "offline"}})
            t.save(p)
            restored = ContextTracker.load(p)
            self.assertEqual(restored.active_topic, "IRAN")
            self.assertEqual(restored.slots["mode"], "offline")

    def test_bounded_short_term_memory(self):
        t = ContextTracker(short_window=8)
        for i in range(50):
            t.observe(str(i), {"entities": [{"text": f"T{i % 5}"}]})
        self.assertEqual(len(t.short_history), 8)
        self.assertLessEqual(len(t.topics), 12)
        self.assertEqual(t.short_history[-1], "49")


if __name__ == "__main__":
    unittest.main()
