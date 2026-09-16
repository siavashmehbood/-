import tempfile
import unittest
from pathlib import Path

from core.atomspace_graph import AtomSpace
from knowledge.knowledge_graph import KnowledgeGraph


class AtomSpaceTests(unittest.TestCase):
    def make_graph(self):
        return KnowledgeGraph(Path(tempfile.mkdtemp()) / "knowledge.json")

    def test_typed_atoms_and_links(self):
        graph = self.make_graph()
        atoms = AtomSpace(graph)
        atoms.observe_fact("ایران", "پایتخت", "تهران", .95, "test")
        self.assertTrue(any(a.name == "ایران" and a.atom_type == "ConceptNode" for a in atoms.atoms()))
        links = atoms.query(relation="پایتخت", source="ایران", target="تهران")
        self.assertEqual(len(links), 1)
        self.assertGreaterEqual(links[0].truth.confidence, .95)

    def test_multi_hop_inference(self):
        graph = self.make_graph()
        atoms = AtomSpace(graph)
        atoms.observe_fact("ایران", "قاره", "آسیا", .9, "test")
        atoms.observe_fact("آسیا", "بخشی_از", "زمین", .8, "test")
        inferred = atoms.infer("ایران", depth=2)
        self.assertTrue(any(x["link"].target == "زمین" for x in inferred))

    def test_snapshot(self):
        graph = self.make_graph()
        atoms = AtomSpace(graph)
        atoms.add_node("ایران", "ConceptNode", .99)
        snap = atoms.snapshot()
        self.assertGreaterEqual(snap["atoms"], 1)
        self.assertGreaterEqual(snap["facts"], 1)


if __name__ == "__main__":
    unittest.main()
