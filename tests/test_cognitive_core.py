import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from core.cognition_engine import CognitiveEngine
from core.world_model import WorldModel
from core.prediction import PredictionEngine
from core.anomaly import AnomalyDetector
from memory.store import Memory
from knowledge.knowledge_graph import KnowledgeGraph
from learning.learning_engine import LearningEngine
from core.kernel import CognitiveKernel

class CognitiveCoreTests(unittest.TestCase):
    def test_kernel_requires_canonical_owner(self):
        with TemporaryDirectory() as d:
            m=Memory(Path(d)/'m.db'); w=WorldModel(Path(d)/'w.json'); k=KnowledgeGraph(Path(d)/'k.json')
            p=PredictionEngine(); a=AnomalyDetector()
            kernel=CognitiveKernel(m,w,k,p,a)
            with self.assertRaisesRegex(RuntimeError,'compatibility adapter'):
                kernel.cycle('inspect project')
            m.close()
    def test_language_snapshot(self):
        s=CognitiveEngine().analyze('میخوام ایران را بسازی بدون اتصال خارجی')
        self.assertEqual(s.intent,'build'); self.assertTrue(s.needs_tools); self.assertTrue(s.constraints)

if __name__=='__main__': unittest.main()

