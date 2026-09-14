import unittest
from core.language_engine import PersianLanguageEngine
from core.brain import Brain
from providers.iran import IranProvider

class NewCoreTests(unittest.TestCase):
    def test_language(self):
        e=PersianLanguageEngine(); a=e.analyze('چرا این پروژه کند است و خطا دارد؟')
        self.assertEqual(a.intent,'question'); self.assertTrue(a.questions); self.assertTrue(e.detect_negation('این کار نمی‌شود'))
    def test_brain(self):
        b=Brain(IranProvider()); self.assertEqual(b.analyze('وضعیت پروژه را بررسی کن').intent,'inspection')
        self.assertTrue(b.health()['ok'])

if __name__=='__main__': unittest.main()

