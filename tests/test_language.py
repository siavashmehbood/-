import unittest
from core.language_engine import PersianLanguageEngine
from providers.iran import IranProvider
from core.reasoning import Reasoner

class LanguageTests(unittest.TestCase):
    def test_persian_normalization(self):
        a=PersianLanguageEngine().analyze('میخوام ایران را بسازی و بعد خطاها را بررسی کنی')
        self.assertEqual(a.intent,'build')
        self.assertIn('ایران',a.entities)
        self.assertGreater(a.confidence,.8)

    def test_reasoning_hypotheses(self):
        r=Reasoner().analyze('چرا پروژه کار نمی‌کند؟')
        self.assertEqual(r.intent,'debug')
        self.assertGreaterEqual(len(r.hypotheses),3)

    def test_semantic_helpers(self):
        e=PersianLanguageEngine()
        self.assertGreater(e.semantic_score('پروژه ایران','ایران پروژه قوی'),.5)
        self.assertEqual(e.summarize('یکی دو سه'), 'یکی دو سه')

    def test_local_brain(self):
        p=IranProvider()
        self.assertIn('ایران',p.generate([{'role':'user','content':'سلام'}]))
        self.assertIn('هدف',p.generate([{'role':'user','content':'میخوام یک سیستم بسازی'}]))

if __name__=='__main__': unittest.main()





