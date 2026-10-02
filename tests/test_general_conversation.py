"""General conversation acceptance through the public IranRuntime path."""
import json,shutil,tempfile,unittest
from pathlib import Path
from runtime.app import IranRuntime
from core.conversational_understanding import ConversationalUnderstanding

SRC=Path(__file__).resolve().parents[1]
class GeneralConversationTests(unittest.TestCase):
    def runtime(self):
        root=Path(tempfile.mkdtemp(prefix="iran_conv_")); shutil.copy(SRC/"config.json",root/"config.json")
        shutil.copytree(SRC/"data",root/"data"); (root/"logs").mkdir(exist_ok=True)
        (root/"data"/"conversation_state.json").unlink(missing_ok=True)
        cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig")); cfg["memory"]["db"]="data/test.db"; cfg["runtime"]["event_log"]="logs/events.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8"); return IranRuntime(root)
    def test_unseen_social_paraphrases_are_dialogue_acts(self):
        u=ConversationalUnderstanding()
        self.assertEqual(u.analyze("سلام خوبی؟").dialogue_act,"greeting")
        self.assertEqual(u.analyze("درود دوست من").dialogue_act,"greeting")
        self.assertEqual(u.analyze("مرسی").dialogue_act,"gratitude")
    def test_colloquial_normalization_preserves_meaning(self):
        u=ConversationalUnderstanding()
        self.assertEqual(u.normalize("میخام بدونم چجوری کار میکنه"),"می‌خواهم بدونم چطور کار میکنه")
    def test_public_runtime_social_followup_and_style(self):
        r=self.runtime()
        try:
            a=r.handle("سلام خوبی؟"); self.assertIn("سلام",a)
            r.handle("پایتون چیه؟")
            b=r.handle("ساده‌تر بگو"); self.assertTrue("ساده" in b or "پایتون" in b)
            c=r.handle("مثال بزن"); self.assertNotIn("UNKNOWN:",c)
        finally:r.close()
    def test_topic_switch_and_return(self):
        r=self.runtime()
        try:
            r.handle("پایتون چیه؟"); first=r.conversation_snapshot().get("current_topic","")
            r.handle("Django چیه؟"); second=r.conversation_snapshot().get("current_topic","")
            self.assertNotEqual(first,second)
            a=r.handle("برگردیم بحث قبلی")
            self.assertTrue(first in a or first in r.conversation_snapshot().get("current_topic",""))
        finally:r.close()
    def test_unknown_is_honest(self):
        r=self.runtime()
        try:
            a=r.handle("دمای دقیق هسته مشتری در سال ۱۴۲۰ چند است؟")
            self.assertTrue("UNKNOWN" in a or "اطلاعات کافی" in a or "نمی‌خواهم حدس" in a)
        finally:r.close()
    def test_meta_uses_actual_state(self):
        r=self.runtime()
        try:
            r.handle("پایتون چیه؟"); a=r.handle("تو چی جواب دادی؟")
            self.assertNotIn("تاریخچه",a); self.assertTrue(len(a)>5)
        finally:r.close()
    def test_learning_request_routes_to_governed_mission(self):
        r=self.runtime()
        try:
            before=len(r.learning_missions.list())
            a=r.handle("پایتون رو از صفر تا صد یاد بگیر")
            after=r.learning_missions.list()
            self.assertGreater(len(after),before)
            self.assertIn("مأموریت",a)
            self.assertIn("learning:",r.conversation_snapshot().get("active_goal",""))
            self.assertEqual(after[-1].get("status"),"active")
            self.assertEqual(after[-1].get("approved_learning_ids"),[])
        finally:r.close()

    def test_restart_restores_conversation_state(self):
        r=self.runtime(); root=r.root
        try:r.handle("پایتون چیه؟")
        finally:r.close()
        r2=IranRuntime(root)
        try:self.assertTrue(r2.conversation_snapshot().get("current_topic"))
        finally:r2.close()
if __name__=="__main__":unittest.main()
