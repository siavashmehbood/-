import unittest,tempfile,json,shutil
from pathlib import Path
from core.rasa_foundation import RasaFoundationAdapter
from core.conversational_understanding import ConversationalUnderstanding
from runtime.app import IranRuntime

SRC=Path(__file__).resolve().parents[1]

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

    def test_persistence_replays_after_restart(self):
        path=Path(tempfile.mkdtemp())/"events.json"
        a=RasaFoundationAdapter(path=path); a.set_slot("topic","پایتون"); a.record_outcome("DIRECT","PASS"); a.save()
        b=RasaFoundationAdapter(path=path)
        self.assertEqual(b.current_state()["slots"]["topic"],"پایتون")
        self.assertEqual(b.current_state()["previous_action"],"DIRECT")

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

    def make_runtime(self):
        root=Path(tempfile.mkdtemp(prefix="iran_rasa_runtime_"))
        shutil.copy(SRC/"config.json",root/"config.json")
        shutil.copytree(SRC/"data",root/"data")
        (root/"logs").mkdir(exist_ok=True)
        (root/"data"/"conversation_state.json").unlink(missing_ok=True)
        (root/"data"/"conversation_events.json").unlink(missing_ok=True)
        cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/test.db"; cfg["runtime"]["event_log"]="logs/events.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
        return IranRuntime(root)

    def test_runtime_black_box_every_turn_reaches_foundation_without_decision_ownership(self):
        r=self.make_runtime()
        try:
            turns=[
                "سلام رفیق، اوضاع چطوره؟",
                "راجع به پایتون یه توضیح ساده بده",
                "همون قبلی رو ادامه بده",
                "نه، منظورم خود زبان پایتون بود",
                "حالا یه لحظه درباره ویندوز حرف بزنیم",
                "برگردیم موضوع قبلی",
                "What is Python used for?",
                "این یکی دقیقاً یعنی چی؟",
            ]
            before=len(r.cognitive_system.pipeline.conversation_foundation.current_state()["events"])
            for text in turns:
                answer=r.handle(text)
                self.assertTrue(str(answer).strip())
                self.assertEqual(r.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
            fs=r.cognitive_system.pipeline.conversation_foundation.current_state()
            self.assertGreaterEqual(len(fs["events"])-before,len(turns)*2)
            self.assertFalse(any(hasattr(r.cognitive_system.pipeline.conversation_foundation,n)
                                 for n in ("decide","predict_action","choose_tool","generate_answer","execute")))
        finally:r.close()

    def test_runtime_restart_replays_foundation_and_conversation_state(self):
        r=self.make_runtime(); root=r.root
        try:
            r.handle("موضوع اصلی ما یادگیری پایتون است.")
            r.handle("همون قبلی رو ادامه بده")
            fs1=r.cognitive_system.pipeline.conversation_foundation.current_state()
            snap1=r.conversation_snapshot()
            self.assertTrue(fs1["events"])
        finally:r.close()
        r2=IranRuntime(root)
        try:
            fs2=r2.cognitive_system.pipeline.conversation_foundation.current_state()
            snap2=r2.conversation_snapshot()
            self.assertGreaterEqual(len(fs2["events"]),len(fs1["events"]))
            self.assertEqual(snap2.get("current_topic"),snap1.get("current_topic"))
            self.assertEqual(r2.cognitive_system.architecture_contract()["parallel_decision_paths"],False)
        finally:r2.close()

    def test_tool_request_stays_subordinate_to_cognitive_system(self):
        r=self.make_runtime()
        try:
            answer=r.handle("get system information")
            self.assertTrue(str(answer).strip())
            self.assertEqual(r.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
            self.assertFalse(hasattr(r.cognitive_system.pipeline.conversation_foundation,"choose_tool"))
        finally:r.close()

if __name__=="__main__":unittest.main()
