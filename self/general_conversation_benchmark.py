"""30-category conversational benchmark using the public runtime path."""
import json,re,shutil,tempfile
from pathlib import Path
from runtime.app import IranRuntime
CATEGORIES=("greetings","casual","persistent_style","factual","explanation","comparison","follow_up","reference","ellipsis","correction","topic_switch",
"return_topic","simple_follow_up","ambiguity","clarification","reasoning","memory","unknown","tool_request","computer_continuity","learning_intent",
"meta","colloquial","noisy_persian","mixed","length","contradiction","feedback","incomplete","multi_turn_goal","unsupported","long_stability")
class GeneralConversationBenchmark:
    def _runtime(self):
        src=Path(__file__).resolve().parents[1]; root=Path(tempfile.mkdtemp(prefix="iran_gcb_"))
        shutil.copy(src/"config.json",root/"config.json"); shutil.copytree(src/"data",root/"data"); (root/"logs").mkdir()
        (root/"data"/"conversation_state.json").unlink(missing_ok=True)
        cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig")); cfg["memory"]["db"]="data/gcb.db"; cfg["runtime"]["event_log"]="logs/gcb.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8"); return IranRuntime(root)
    def run(self):
        r=self._runtime(); details=[]
        def check(cat,fn):
            try: ok,evidence=fn(); details.append({"category":cat,"ok":bool(ok),"evidence":str(evidence)[:300]})
            except Exception as exc: details.append({"category":cat,"ok":False,"evidence":type(exc).__name__+":"+str(exc)[:180]})
        try:
            check("greetings",lambda:(("سلام" in (a:=r.handle("درود دوست من"))),a))
            check("casual",lambda:((len(a:=r.handle("امروز یکم خسته‌ام"))>3),a))
            def persistent_short_style():
                ordinary=self._runtime()
                styled=self._runtime()
                try:
                    ordinary.handle("امروز واقعاً خسته‌ام")
                    default_answer=ordinary.handle("الان هم خسته‌ام")
                    styled.handle("از این به بعد کوتاه جواب بده")
                    styled.handle("امروز واقعاً خسته‌ام")
                    short_answer=styled.handle("الان هم خسته‌ام")
                    content_kept=any(term in short_answer for term in ("خسته","حالت","استراحت","کنارت","گوش می‌دم","همراهت"))
                    evidence={"default_answer":default_answer,"styled_answer":short_answer}
                    return bool(content_kept and len(short_answer)<len(default_answer) and "UNKNOWN" not in short_answer),evidence
                finally:
                    ordinary.close()
                    styled.close()
            check("persistent_style",persistent_short_style)
            check("factual",lambda:(("زبان" in (a:=r.handle("پایتون چیه؟"))),a))
            check("explanation",lambda:(("UNKNOWN" not in (a:=r.handle("چرا؟"))),a))
            check("comparison",lambda:((len(a:=r.handle("فرق پایتون و Django چیه؟"))>5),a))
            check("follow_up",lambda:(("UNKNOWN" not in (a:=r.handle("ادامه بده"))),a))
            check("reference",lambda:((len(a:=r.handle("همون قبلی رو بیشتر توضیح بده"))>5),a))
            check("ellipsis",lambda:(("UNKNOWN" not in (a:=r.handle("و برای ویندوز؟"))),a))
            check("correction",lambda:(("ویندوز" in (a:=r.handle("نه منظورم ویندوز بود"))),a))
            r.handle("پایتون چیه؟"); before=r.conversation_snapshot().get("current_topic",""); r.handle("Django چیه؟")
            check("topic_switch",lambda:((r.conversation_snapshot().get("current_topic","")!=before),r.conversation_snapshot()))
            def topic_round_trip():
                isolated=self._runtime()
                try:
                    isolated.handle("پایتون چیه؟")
                    first=isolated.conversation_snapshot().get("current_topic","")
                    second_answer=isolated.handle("ویندوز چیه؟")
                    second_snapshot=isolated.conversation_snapshot()
                    second=second_snapshot.get("current_topic","")
                    answer=isolated.handle("برگردیم بحث قبلی")
                    returned_snapshot=isolated.conversation_snapshot()
                    returned=returned_snapshot.get("current_topic","")
                    evidence={"first_topic":first,"second_topic":second,"second_answer":second_answer,"second_answer_type":second_snapshot.get("last_answer_type"),"second_question":second_snapshot.get("current_question"),"topic_stack":second_snapshot.get("topic_stack"),"returned_topic":returned,"answer":answer}
                    return bool(first and second and first!=second and returned==first and "UNKNOWN" not in answer),evidence
                finally:
                    isolated.close()
            check("return_topic",topic_round_trip)
            check("ambiguity",lambda:((any(x in (a:=r.handle("اون یکی رو انجام بده")) for x in ("کدام","کدوم","مشخص","منظور"))),a))
            check("clarification",lambda:(("UNKNOWN" not in (a:=r.handle("یعنی چی؟"))),a))
            check("reasoning",lambda:((len(a:=r.handle("اگر برعکسش کنیم چی؟"))>3),a))
            check("memory",lambda:(("UNKNOWN" not in (a:=r.handle("بحثمون سر چی بود؟"))),a))
            check("unknown",lambda:((any(x in (a:=r.handle("دمای دقیق هسته مشتری در سال ۱۴۲۰ چند است؟")) for x in ("UNKNOWN","اطلاعات کافی","حدس"))),a))
            check("tool_request",lambda:((len(a:=r.handle("اطلاعات سیستم رو بگو"))>3),a))
            check("computer_continuity",lambda:((len(a:=r.handle("حالا ادامه بده"))>3),a))
            check("learning_intent",lambda:((bool(r.handle("پایتون رو از صفر تا صد یاد بگیر")) and bool(r.conversation_snapshot().get("active_goal",""))),r.conversation_snapshot().get("active_goal","")))
            check("meta",lambda:(("جواب" in (a:=r.handle("تو چی جواب دادی؟")) and "هنوز جواب قبلی ثبت نشده" not in a),a))
            check("colloquial",lambda:((len(a:=r.handle("میخام بدونم چجوری کار میکنه"))>3),a))
            check("noisy_persian",lambda:((len(a:=r.handle("ميخوام  پایتون رو بفهمم"))>3),a))
            check("mixed",lambda:((len(a:=r.handle("Python برای پروژه IRAN خوبه؟"))>3),a))
            r.handle("پایتون یک زبان برنامه‌نویسی است")
            def concise_follow_up():
                source=r.conversation_snapshot().get("last_assistant_answer","")
                answer=r.handle("کوتاه بگو")
                source_terms=set(re.findall(r"[\w]{3,}",source))
                answer_terms=set(re.findall(r"[\w]{3,}",answer))
                framing=re.findall(r"(?:خلاصه|پاسخ مستقیم|پاسخ کوتاه)\s*:",answer)
                retained=len(source_terms & answer_terms)
                evidence={"source":source,"answer":answer,"shared_content_terms":retained,"framing_labels":framing}
                return bool(answer and len(answer)<300 and retained>=2 and len(framing)<=1),evidence
            check("length",concise_follow_up)
            def simple_follow_up():
                isolated=self._runtime()
                try:
                    isolated.handle("پایتون چیه؟")
                    isolated.handle("چرا؟")
                    source=isolated.conversation_snapshot().get("last_assistant_answer","")
                    answer=isolated.handle("ساده‌تر بگو")
                    evidence={"source":source,"answer":answer}
                    clear_terms=all(term not in answer for term in ("سطح‌بالا","سطح بالا","چندمنظوره"))
                    grounded_plain_language=("پایتون" in answer and "کار" in answer and ("لازم نیست" in answer or "نیازی نیست" in answer))
                    return bool(source and answer!=source and clear_terms and grounded_plain_language and "؟" not in answer),evidence
                finally:
                    isolated.close()
            check("simple_follow_up",simple_follow_up)
            check("contradiction",lambda:((len(a:=r.handle("نه، منظورم این نبود"))>3),a))
            check("feedback",lambda:((len(a:=r.handle("اشتباه فهمیدی"))>3),a))
            check("incomplete",lambda:(("UNKNOWN" not in (a:=r.handle("بعدش؟"))),a))
            r.handle("می‌خوام پایتون یاد بگیرم"); r.handle("از صفرم")
            check("multi_turn_goal",lambda:((bool(r.conversation_snapshot().get("active_goal",""))),r.conversation_snapshot()))
            check("unsupported",lambda:((any(x in (a:=r.handle("یک واقعیت ناشناخته و بدون شاهد درباره سیاره XQZ بگو")) for x in ("UNKNOWN","اطلاعات","حدس"))),a))
            for m in ("پایتون چیه؟","چرا؟","مثال بزن","Django چیه؟","برگردیم بحث قبلی","ادامه بده","کوتاه بگو","مطمئنی؟","نه منظورم قبلی بود","حالا ادامه بده"): r.handle(m)
            check("long_stability",lambda:((r.conversation_snapshot().get("turns",0)>=10),r.conversation_snapshot().get("turns")))
        finally:r.close()
        passed=sum(int(x["ok"]) for x in details); return {"cases":len(details),"passed":passed,"score":round(100*passed/len(details),2),"pass":passed==len(details),"details":details}
if __name__=="__main__":
    result=GeneralConversationBenchmark().run(); print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["pass"] else 1)
