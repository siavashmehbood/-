import unittest
from core.context_tracker import ContextTracker


class ContextTrackerBenchmark40(unittest.TestCase):
    def test_40_context_invariants(self):
        tracker = ContextTracker(max_topics=12, short_window=8)
        cases = [
            ({"entities":[{"text":"Django"}]}, "", "Django"),
            ({"entities":[{"text":"Python"}]}, "", "Python"),
            ({"entities":[{"text":"IRAN"}]}, "", "IRAN"),
            ({"entities":[{"text":"حافظه"}]}, "", "حافظه"),
            ({"goal":"معماری شناختی"}, "", "معماری شناختی"),
            ({"goal":"گفتگو"}, "", "گفتگو"),
            ({"entities":[{"text":"Django"}]}, "", "Django"),
            ({"entities":[{"text":"Python"}]}, "", "Python"),
            ({"entities":[{"text":"Django"}]}, "", "Django"),
            ({"entities":[{"text":"IRAN"}]}, "", "IRAN"),
        ]
        for i in range(4):
            for j, (parsed, resolved, expected) in enumerate(cases):
                snap = tracker.observe(f"turn-{i}-{j}", parsed, resolved)
                self.assertTrue(snap.active_topic)
                self.assertLessEqual(len(snap.topics), 12)
                self.assertLessEqual(len(snap.short_history), 8)

        tracker.observe("reference", {}, "Django")
        self.assertEqual(tracker.resolve(), "Django")
        tracker.observe("slot turn", {"entities": [{"text": "Django"}], "slots": {"language": "Python", "mode": "offline"}})
        snap = tracker.snapshot()
        self.assertEqual(snap.active_topic, "Django")
        self.assertEqual(snap.slots["language"], "Python")
        self.assertEqual(snap.slots["mode"], "offline")
        self.assertEqual(len(snap.short_history), 8)


if __name__ == "__main__":
    unittest.main()
