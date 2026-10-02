import unittest
from core.rasa_foundation import RasaFoundationAdapter
from core.conversational_understanding import ConversationalUnderstanding

class RasaFoundationTests(unittest.TestCase):
    def test_nlu_contract_and_event_replay(self):
        u=ConversationalUnderstanding()
        a=RasaFoundationAdapter()
        m=u.analyze("درود، بعدش برای ویندوز چی؟")
        msg=a.ingest(m,{})
        self.assertEqual(msg["text"],m.normalized_text)
        self.assertIn("name",msg["intent"]); self.assertIn("confidence",msg["intent"])
        a.set_slot("focus","windows"); a.record_outcome("FOLLOW_UP","PASS")
        restored=RasaFoundationAdapter.replay(a.current_state()["events"])
        self.assertEqual(restored.current_state()["slots"]["focus"],"windows")
        self.assertEqual(restored.current_state()["previous_action"],"FOLLOW_UP")

    def test_foundation_has_no_decision_api(self):
        a=RasaFoundationAdapter()
        for forbidden in ("decide","predict_action","choose_tool","generate_answer","execute"):
            self.assertFalse(hasattr(a,forbidden),forbidden)

    def test_unseen_multi_intent_state_is_structured_not_answered(self):
        u=ConversationalUnderstanding(); a=RasaFoundationAdapter()
        msg=a.ingest(u.analyze("اول پایتون رو توضیح بده، بعد نوت‌پد رو باز کن"))
        self.assertTrue(msg["text"])
        self.assertIsInstance(msg["entities"],list)
        self.assertGreaterEqual(len(a.current_state()["events"]),1)

if __name__=="__main__":unittest.main()
