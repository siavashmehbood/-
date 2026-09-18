import tempfile
import unittest
from pathlib import Path
from core.cognitive_core import AdvancedCognitiveCore

class _Events:
    def emit(self,*a,**k): pass
class _Memory:
    def working_context(self,*a,**k): return [('fact','پایتون زبان برنامه نویسی است','',)]
    def semantic_search(self,*a,**k): return []
class _Knowledge:
    def query(self,*a,**k): return []
class _Dialogue:
    def snapshot(self): return {'topic':'پایتون','goal':'یادگیری'}
class _Runtime:
    memory=_Memory(); knowledge=_Knowledge(); events=_Events(); dialogue=_Dialogue()

class TestAdvancedCognitiveCore(unittest.TestCase):
    def test_typed_state_and_plan(self):
        c=AdvancedCognitiveCore(_Runtime())
        s=c.begin('پایتون چیه؟')
        self.assertEqual(s.turn_id,1)
        self.assertTrue(s.plan)
        self.assertGreaterEqual(s.confidence,0.05)
        self.assertIsInstance(s.snapshot(),dict)
    def test_verification_rejects_meta_output(self):
        c=AdvancedCognitiveCore(_Runtime())
        s=c.begin('پایتون چیه؟')
        v=c.verify(s,'cognitive_cycle language_analysis plan_created')
        self.assertFalse(v['passed'])
    def test_verification_accepts_real_answer(self):
        c=AdvancedCognitiveCore(_Runtime())
        s=c.begin('پایتون چیه؟')
        v=c.verify(s,'پایتون یک زبان برنامه نویسی سطح بالا و چندمنظوره است.')
        self.assertTrue(v['passed'])

if __name__=='__main__': unittest.main()
