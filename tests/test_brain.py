import unittest
from core.brain import Brain
from providers.iran import IranProvider

class BrainTests(unittest.TestCase):
    def test_analysis(self):
        b=Brain(IranProvider()); a=b.analyze('چرا پروژه کار نمی‌کند؟')
        self.assertEqual(a.intent,'debug'); self.assertGreater(a.confidence,.7)
    def test_compare(self):
        b=Brain(IranProvider()); r=b.compare('پروژه ایران خوب است','پروژه ایران قوی است')
        self.assertIn('پروژه',r['shared_terms'])

if __name__=='__main__': unittest.main()

