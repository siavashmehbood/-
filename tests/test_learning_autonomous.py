import json,tempfile,unittest
from pathlib import Path
from learning.learning_engine import LearningEngine

class TestAutonomousLearning(unittest.TestCase):
    def test_repeated_success_creates_rule(self):
        with tempfile.TemporaryDirectory() as d:
            e=LearningEngine(Path(d)/'learning.json')
            e.record('ساخت هسته هوشمند','evidence-first','ok',.9,'build','evidence-first','core')
            e.record('ساخت هسته هوشمند با تست','evidence-first','ok',.95,'build','evidence-first','core')
            self.assertGreaterEqual(len(e.rules),1)
            self.assertEqual(e.recommended_strategy('ساخت هسته هوشمند','build','core'),'evidence-first')

    def test_failure_changes_learning_signal(self):
        with tempfile.TemporaryDirectory() as d:
            e=LearningEngine(Path(d)/'learning.json')
            e.record('رفع خطای حافظه','fast-fix','failed',.2,'debug','fast-fix','memory')
            e.record('رفع خطای حافظه دوباره','fast-fix','failed',.2,'debug','fast-fix','memory')
            self.assertTrue(e.rules)
            self.assertIn('نیاز به تغییر',e.rules[-1]['rule'])

    def test_explicit_feedback_is_learned(self):
        with tempfile.TemporaryDirectory() as d:
            e=LearningEngine(Path(d)/'learning.json')
            out=e.update_from_feedback('پاسخ پروژه','عالی بود','general','general')
            self.assertTrue(out.get('score',0)>.8)
            self.assertEqual(e.stats()['experiences'],1)

    def test_adaptation_contains_rules_and_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            e=LearningEngine(Path(d)/'learning.json')
            e.record('بررسی سیستم','inspect','ok',.9,'inspect','inspect','system')
            result=e.adapt('بررسی سیستم','inspect','system')
            self.assertIn('recommended_strategy',result)
            self.assertIn('learned_rules',result)
            self.assertIn('strategy_evidence',result)

if __name__=='__main__': unittest.main()
