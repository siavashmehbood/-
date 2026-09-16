import unittest

from core.working_memory import SymbolicWorkingMemory
from core.metacognition import MetacognitiveMonitor
from core.causal_reasoning import CausalGraph
from core.analogical_reasoning import AnalogicalReasoner

class CognitiveArchitectureModulesTests(unittest.TestCase):
    def test_working_memory_retrieves_recent_relevant_item(self):
        m = SymbolicWorkingMemory(capacity=4)
        m.add("Python project", salience=.9)
        m.add("unrelated note", salience=.2)
        self.assertEqual(m.recall("Python", 1)[0][1], "Python project")

    def test_working_memory_capacity(self):
        m = SymbolicWorkingMemory(capacity=2)
        for i in range(4): m.add(str(i))
        self.assertEqual(len(m.items), 2)

    def test_metacognition_flags_weak_evidence(self):
        a = MetacognitiveMonitor().assess(.3, 0, 0, 0)
        self.assertIn("low_confidence", a.issues)
        self.assertEqual(a.recommendation, "verify")

    def test_causal_graph_path_and_effects(self):
        g = CausalGraph(); g.add("rain", "wet"); g.add("wet", "slippery")
        self.assertEqual(g.path("rain", "slippery"), ["rain", "wet", "slippery"])
        self.assertIn("slippery", g.effects("rain"))

    def test_analogical_matching_is_explainable(self):
        r = AnalogicalReasoner().compare({"cause":"rain", "effect":"wet"}, {"cause":"rain", "effect":"dry"})
        self.assertEqual(r.shared, ["cause"])
        self.assertGreater(r.score, 0)

if __name__ == "__main__": unittest.main()

