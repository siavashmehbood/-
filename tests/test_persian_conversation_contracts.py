import tempfile
import unittest
from pathlib import Path
from core.conversation_state import ConversationState
from core.conversation_intelligence import ConversationIntelligence


class PersianConversationContractTests(unittest.TestCase):
    def make(self):
        return ConversationState(state_path=str(Path(tempfile.mkdtemp()) / 'state.json'))

    def test_10_reference_cases(self):
        refs = ('این', 'همین', 'اون', 'همون', 'همونو', 'قبلی', 'بالایی', 'این بخش', 'این جواب', 'این مشکل')
        for ref in refs:
            s = self.make(); s.update('پایتون چیه؟', 'پایتون یک زبان است.')
            c = ConversationIntelligence(s).build_context(ref)
            self.assertTrue(c.references or c.current_topic)

    def test_10_correction_cases(self):
        corrections = tuple(f'نه، منظورم حافظه {i} بود.' for i in range(10))
        for text in corrections:
            s = self.make(); s.update('این بخش را توضیح بده.', 'پاسخ')
            s.update(text, 'متوجه شدم.')
            self.assertIn('حافظه', s.current_topic)

    def test_10_unknown_cases_are_unresolved(self):
        for i in range(10):
            s = self.make(); s.update(f'آیا فردا در سیاره ناشناخته {i} باران می‌بارد؟', 'اطلاعات کافی ندارم.')
            self.assertTrue(s.current_question)

    def test_10_multi_intent_cases(self):
        for i in range(10):
            text = f'پایتون چیست و چرا محبوب است و برای پروژه {i} چه فایده‌ای دارد؟'
            c = ConversationIntelligence(self.make()).build_context(text)
            self.assertEqual(c.question_type, 'multi_intent')
            self.assertGreaterEqual(len(c.question_units), 2)

    def test_10_memory_recall_cases(self):
        for i in range(10):
            s = self.make(); s.update(f'پروژه پایتون {i}', 'پاسخ')
            s.update('ادامه بده', 'ادامه')
            self.assertTrue(s.current_topic)

    def test_20_multiturn_dialogues(self):
        for i in range(20):
            s = self.make()
            s.update('پایتون چیه؟', 'پایتون زبان برنامه‌نویسی است.')
            s.update('چرا؟', 'چون خواناست.')
            s.update('برای پروژه من خوبه؟', 'بسته به پروژه.')
            s.update('نه، منظورم حافظه بود.', 'متوجه شدم.')
            self.assertIn('حافظه', s.current_topic)
            self.assertTrue(s.turns)


if __name__ == '__main__':
    unittest.main()
