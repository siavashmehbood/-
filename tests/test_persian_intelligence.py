import unittest
from language_intelligence import PersianIntelligence

class PersianIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.ai = PersianIntelligence()

    def test_raw_and_normalized_are_preserved(self):
        x = self.ai.analyze('يک پروژه ۱۲ مرحله‌ای بساز')
        self.assertEqual(x['raw_text'], 'يک پروژه ۱۲ مرحله‌ای بساز')
        self.assertIn('یک', x['normalized_text'])
        self.assertIn('build', [i['name'] for i in x['intents']])

    def test_multi_intent_and_constraints(self):
        x = self.ai.analyze('سیستم رو بررسی کن، اگر مشکل داشت درستش کن و بعد تست بگیر؛ بدون اینترنت')
        self.assertTrue(x['multi_intent'])
        self.assertTrue(x['constraints'])
        names = {i['name'] for i in x['intents']}
        self.assertTrue(names & {'inspect', 'build', 'command', 'debug'})

    def test_temporal_reference_and_negation(self):
        x = self.ai.analyze('نسخه قبلی را امروز بررسی کن، بدون اینترنت')
        self.assertIn('امروز', x['temporal'])
        self.assertIn('قبلی', x['references'])
        self.assertTrue(x['negations'])

if __name__ == '__main__':
    unittest.main()
