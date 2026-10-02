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

class _Canonical:
    def __init__(self): self.calls=[]
    def advanced_core_compat(self, text):
        self.calls.append(text)
        return {"canonical": True, "input": text}

class TestAdvancedCognitiveCore(unittest.TestCase):
    def make_core(self):
        core = AdvancedCognitiveCore(_Runtime())
        core._canonical_system = _Canonical()
        return core

    def test_begin_delegates_to_canonical_owner(self):
        c=self.make_core()
        s=c.begin('question')
        self.assertEqual(s, {"canonical": True, "input": "question"})
        self.assertEqual(c._canonical_system.calls, ["question"])

    def test_unbound_begin_fails_closed(self):
        c=AdvancedCognitiveCore(_Runtime())
        with self.assertRaisesRegex(RuntimeError,'compatibility adapter'):
            c.begin('question')

if __name__=='__main__': unittest.main()
