import unittest
from pathlib import Path
from core.dialogue import ConversationState, ReferenceResolver, QuestionAnalyzer, AnswerVerifier

class DialogueStateTests(unittest.TestCase):
    def test_reference_phrases(self):
        s=ConversationState(); s.update('پایتون چیست؟','پاسخ',parsed={'question_units':['پایتون چیست؟'],'entities':[{'text':'پایتون'}]})
        r=ReferenceResolver()
        for q in ['این را بهتر کن','این قسمت را بهتر کن','همون قبلی','ادامه بده','بیشتر توضیح بده']:
            self.assertTrue(r.resolve(q,s,[]))
    def test_correction_changes_topic(self):
        s=ConversationState(); s.update('پایتون چیست؟',parsed={'question_units':['پایتون چیست؟'],'entities':[{'text':'پایتون'}]})
        s.update('نه، منظورم حافظه بود',parsed={'question_type':'correction'})
        self.assertIn('حافظه',s.current_topic)
    def test_topic_stack(self):
        s=ConversationState()
        for x in ['پایتون','حافظه','پروژه']:
            s.update(x,parsed={'goal':x,'entities':[{'text':x}]})
        self.assertEqual(s.current_topic,'پروژه')
        self.assertEqual(s.topic_stack[-1],'حافظه')
        self.assertEqual(s.topic_stack[-2],'پایتون')
    def test_compound_split(self):
        p=QuestionAnalyzer().analyze('پایتون چیست و چرا محبوب است و برای پروژه من چه فایده‌ای دارد؟')
        self.assertGreaterEqual(len(p['question_units']),3)

if __name__=='__main__': unittest.main()
