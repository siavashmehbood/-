import tempfile
import unittest
from pathlib import Path

from core.conversation_state import ConversationState
from core.conversation_intelligence import ConversationIntelligence, CognitiveContext


class PersianConversationIntelligenceTests(unittest.TestCase):
    def state(self):
        return ConversationState(state_path=str(Path(tempfile.mkdtemp()) / 'conversation.json'))

    def test_reference_resolution(self):
        s = self.state(); s.update('پایتون چیه؟', 'پایتون یک زبان برنامه‌نویسی است.')
        ci = ConversationIntelligence(s)
        c = ci.build_context('چرا؟')
        self.assertEqual(c.question_type, 'why')
        self.assertTrue(c.current_topic)

    def test_correction(self):
        s = self.state(); s.update('این بخش رو توضیح بده.', 'پاسخ')
        s.update('نه، منظورم حافظه بود.', 'متوجه شدم؛ حافظه را بررسی می‌کنیم.')
        self.assertIn('حافظه', s.current_topic)
        self.assertIn('حافظه', s.correction)

    def test_topic_stack_restore(self):
        s = self.state(); s.update('پایتون چیه؟', 'پاسخ پایتون')
        s.update('حافظه چیه؟', 'پاسخ حافظه')
        restored = s.restore_previous_topic()
        self.assertIn('پایتون', restored)

    def test_followup_plan(self):
        s = self.state(); s.update('پایتون چیه؟', 'پاسخ')
        c = ConversationIntelligence(s).build_context('ادامه بده')
        self.assertEqual(c.question_type, 'follow_up')
        self.assertTrue(c.answer_plan)

    def test_unknown_verifier_does_not_force_pass(self):
        s = self.state()
        c = CognitiveContext('یک سؤال ناشناخته درباره چیزی که در دانش محلی نیست', question_type='question', confidence=.2)
        v = ConversationIntelligence(s).verifier.verify(c, '')
        self.assertEqual(v.status, 'REPAIR')


if __name__ == '__main__':
    unittest.main()
