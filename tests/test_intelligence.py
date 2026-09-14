import unittest
from core.intelligence import Intelligence
class IntelligenceTests(unittest.TestCase):
    def test_classification(self):
        x=Intelligence(); self.assertEqual(x.classify('ساعت الان چنده'),'system_time'); self.assertEqual(x.classify('ساختار پروژه را نشان بده'),'project_inspection'); self.assertEqual(x.classify('چی گفتم؟'),'memory_recall')
    def test_decision(self):
        d=Intelligence().decide('مشخصات سیستم'); self.assertEqual(d.intent,'system_info'); self.assertGreater(d.confidence,.9)
if __name__=='__main__': unittest.main()
