"""Phase-1 semantic intelligence black-box acceptance.

All cases enter through IranRuntime -> CognitiveSystem. Names are intentionally
not fixture vocabulary and facts are stated without "remember this".
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime

SRC = Path(__file__).resolve().parents[1]


class SemanticIntelligenceAcceptance(unittest.TestCase):
    def runtime(self):
        root=Path(tempfile.mkdtemp(prefix="iran_semantic_phase1_"))
        shutil.copy(SRC/"config.json",root/"config.json")
        shutil.copytree(SRC/"data",root/"data")
        (root/"logs").mkdir(exist_ok=True)
        for p in (
            root/"data"/"conversation_state.json",
            root/"data"/"conversation_events.json",
            root/"data"/"context_tracker.json",
            root/"data"/"test-semantic.db",
        ):
            p.unlink(missing_ok=True)
        cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/test-semantic.db"
        cfg["runtime"]["event_log"]="logs/events.jsonl"
        cfg["runtime"]["goals"]="data/goals.json"
        (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
        return IranRuntime(root)

    def assert_value(self,answer,value):
        self.assertIn(value,answer)
        self.assertFalse(str(answer).startswith("UNKNOWN:"),answer)

    def test_scenario_a_project_semantic_reference(self):
        r=self.runtime()
        try:
            r.handle("من روی پروژه‌ای به اسم آریانا کار می‌کنم.")
            r.handle("حالا درباره ویندوز حرف بزنیم.")
            self.assert_value(r.handle("اون پروژه‌ای که گفتم اسمش چی بود؟"),"آریانا")
            self.assert_value(r.handle("پروژه‌ای که روش کار می‌کنم چی بود؟"),"آریانا")
        finally:r.close()

    def test_scenario_b_person_relation(self):
        r=self.runtime()
        try:
            r.handle("یکی از همکارام اسمش نیماست.")
            r.handle("امروز درباره تست نرم‌افزار حرف بزنیم.")
            self.assert_value(r.handle("اسم همکارم چی بود؟"),"نیما")
        finally:r.close()

    def test_scenario_c_preference_after_topic_switch(self):
        r=self.runtime()
        try:
            r.handle("من قهوه تلخ رو بیشتر دوست دارم.")
            r.handle("حالا درباره لینوکس صحبت کنیم.")
            self.assert_value(r.handle("من قهوه رو چطوری دوست داشتم؟"),"تلخ")
        finally:r.close()

    def test_scenario_d_correction_supersedes_without_deleting_history(self):
        r=self.runtime()
        try:
            r.handle("اسم محصولمون سپهره.")
            r.handle("نه، اسمش رو گذاشتیم سپهر نو.")
            answer=r.handle("اسم محصول چیه؟")
            self.assert_value(answer,"سپهر نو")
            rows=r.memory.conn.execute(
                "SELECT value FROM semantic_facts WHERE predicate='name' AND subject LIKE 'product:%' ORDER BY updated_at"
            ).fetchall()
            values=[x[0] for x in rows]
            self.assertIn("سپهر",values)
            self.assertIn("سپهر نو",values)
        finally:r.close()

    def test_scenario_e_multiple_entities_resolve_independently(self):
        r=self.runtime()
        try:
            r.handle("من روی پروژه‌ای به اسم باران کار می‌کنم که برای فروش کتاب است.")
            r.handle("من روی پروژه‌ای به اسم آذرخش کار می‌کنم که برای مدیریت صوت است.")
            r.handle("یکی از همکارام اسمش کیان است.")
            r.handle("یکی از دوستام اسمش رادین است.")
            r.handle("اسم محصولمون ماهوره.")
            self.assert_value(r.handle("اسم همکارم چی بود؟"),"کیان")
            self.assert_value(r.handle("اسم دوستم چی بود؟"),"رادین")
            self.assert_value(r.handle("اسم محصول چیه؟"),"ماهور")
            self.assert_value(r.handle("اسم پروژه اول چی بود؟"),"باران")
            self.assert_value(r.handle("اسم پروژه دوم چی بود؟"),"آذرخش")
            self.assert_value(r.handle("پروژه باران برای چی بود؟"),"فروش کتاب")
            self.assert_value(r.handle("پروژه آذرخش برای چی بود؟"),"مدیریت صوت")
        finally:r.close()

    def test_scenario_f_topic_switch_and_return(self):
        r=self.runtime()
        try:
            r.handle("روی پروژه‌ای به اسم نارون کار می‌کنم.")
            r.handle("حالا درباره شبکه حرف بزنیم.")
            r.handle("بعدش درباره پایتون.")
            self.assert_value(r.handle("برگردیم به پروژه قبلی، اسمش چی بود؟"),"نارون")
        finally:r.close()

    def test_scenario_g_restart_durable_fact(self):
        r=self.runtime()
        root=r.root
        try:
            r.handle("من روی پروژه‌ای به اسم کاویان کار می‌کنم.")
        finally:r.close()
        r2=IranRuntime(root)
        try:
            self.assert_value(r2.handle("پروژه‌ای که روش کار می‌کردم اسمش چی بود؟"),"کاویان")
            self.assertEqual(r2.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
        finally:r2.close()

    def test_scenario_h_unknown_names_and_paraphrases(self):
        r=self.runtime()
        try:
            r.handle("دارم روی پروژه ای به نام زوبین کار میکنم.")
            self.assert_value(r.handle("اون پروژه اسمش چه بود؟"),"زوبین")
            r.handle("اسم شرکت من آفتاب است.")
            self.assert_value(r.handle("نام شرکتم چی بود؟"),"آفتاب")
        finally:r.close()

    def test_real_gui_failure_no_raw_echo(self):
        r=self.runtime()
        try:
            r.handle("دارم روی یه پروژه به اسم دانا کار می‌کنم که برای کتابه.")
            r.handle("من سازندتم.")
            r.handle("من می‌خوام به تو کمک کنم که قوی بشی.")
            answer=r.handle("پروژه‌ای که روش کار می‌کنم چی بود؟")
            self.assert_value(answer,"دانا")
            self.assertNotIn("پروژه‌ای که روش کار می‌کنم چی بود",answer)
            answer2=r.handle("نه منظورم اسم پروژه بود.")
            self.assert_value(answer2,"دانا")
        finally:r.close()

    def test_adversarial_normalization_and_short_followups(self):
        r=self.runtime()
        try:
            r.handle("روی پروژه‌ای به اسم ژرفا کار می‌كنم.")
            self.assert_value(r.handle("اسمش؟"),"ژرفا")
            r.handle("نه، اسمش رو گذاشتیم ژرفای نو.")
            self.assert_value(r.handle("همون قبلی، اسمش چی شد؟"),"ژرفای نو")
        finally:r.close()

    def test_questions_speculation_and_uncertainty_do_not_become_facts(self):
        r=self.runtime()
        try:
            r.handle("شاید اسم پروژه بعدی مهتاب باشد.")
            r.handle("اگر اسم پروژه فرضی شهاب باشد چه؟")
            r.handle("اسم پروژه من چیه؟")
            rows=r.memory.conn.execute(
                "SELECT value FROM semantic_facts WHERE predicate='name' AND subject LIKE 'project:%'"
            ).fetchall()
            values={x[0] for x in rows}
            self.assertNotIn("مهتاب",values)
            self.assertNotIn("شهاب",values)
        finally:r.close()

    def test_anti_echo_blocks_previous_question_as_answer(self):
        r=self.runtime()
        try:
            q="این موضوع ناشناخته دقیقاً چه نامی داشت؟"
            a=r.handle(q)
            self.assertNotEqual(a.strip(),q.strip())
            r.handle("یک سؤال دیگر دارم.")
            b=r.handle("من چند لحظه پیش چه سؤال ناشناخته‌ای پرسیدم؟")
            self.assertNotEqual(b.strip(),q.strip())
        finally:r.close()

    def test_backend_contract_is_offline_and_framework_optional(self):
        r=self.runtime()
        try:
            status=r.cognitive_system.pipeline.semantic_intelligence.backend_status()
            self.assertTrue(status["offline"])
            self.assertFalse(status["runtime_downloads"])
            self.assertEqual(status["decision_owner"],"CognitiveSystem")
            self.assertEqual(status["active"],"fallback")
            for name in ("spacy","stanza","deeppavlov","haystack"):
                self.assertIn(name,status["optional"])
        finally:r.close()

    def test_semantic_trace_and_rasa_consistency(self):
        r=self.runtime()
        try:
            r.handle("من روی پروژه‌ای به اسم روشنا کار می‌کنم.")
            trace=r.cognitive_system.pipeline.engine.last_semantic_trace
            self.assertGreaterEqual(len(trace["facts"]),2)
            self.assertTrue(any(x["relation"]=="name" for x in trace["facts"]))
            fs=r.cognitive_system.pipeline.conversation_foundation.current_state()
            self.assertTrue(str(fs["slots"].get("semantic.last_entity","")).startswith("project:"))
            self.assertEqual(r.cognitive_system.architecture_contract()["parallel_decision_paths"],False)
        finally:r.close()


if __name__=="__main__":
    unittest.main()
