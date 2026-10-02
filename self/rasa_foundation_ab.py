"""Independent A/B benchmark for current IRAN vs the Rasa-foundation state contract."""
import json,shutil,tempfile,time
from pathlib import Path
from runtime.app import IranRuntime

UNSEEN=[
"درود رفیق، حالت چطوره؟","راجع به پایتون یه توضیح ساده بده","چرا؟","یه نمونه دیگه بزن",
"نه، منظورم خود زبان پایتون بود","حالا Django رو مقایسه کن","دومی دقیقاً چه کاربردی داره؟",
"برگردیم بحث قبل","کوتاه‌تر بگو","اگر اینترنت قطع باشه چی؟","این حرفت بر چه اساسی بود؟",
"موضوع اصلی ما یادگیری برنامه‌نویسی است","یه لحظه درباره ویندوز حرف بزنیم","برگردیم موضوع قبلی",
"اون یکی رو انجام بده","نه همونی که قبل‌تر گفتیم","بعدش؟","برای لینوکس چطور؟",
"منظورت از این بخش چیه؟","پایتون رو از صفر تا صد یاد بگیر",
]
LONG=[UNSEEN[i%len(UNSEEN)] for i in range(40)]

def runtime():
    src=Path(__file__).resolve().parents[1]; root=Path(tempfile.mkdtemp(prefix="iran_rasa_ab_"))
    shutil.copy(src/"config.json",root/"config.json"); shutil.copytree(src/"data",root/"data"); (root/"logs").mkdir()
    (root/"data"/"conversation_state.json").unlink(missing_ok=True)
    cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig")); cfg["memory"]["db"]="data/ab.db"; cfg["runtime"]["event_log"]="logs/ab.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
    return IranRuntime(root)

def run():
    r=runtime(); rows=[]; started=time.perf_counter()
    try:
        for i,msg in enumerate(LONG):
            answer=r.handle(msg); trace=getattr(r.cognitive_system,"last_trace",None)
            foundation=getattr(r.cognitive_system.pipeline,"conversation_foundation",None)
            fs=foundation.current_state() if foundation else {}
            rows.append({"turn":i+1,"input":msg,"nonempty":bool(answer.strip()),
              "unknown":answer.startswith("UNKNOWN:"),"verification":getattr(trace,"verification_status",""),
              "topic":r.conversation_snapshot().get("current_topic",""),
              "foundation_events":len(fs.get("events",[])),"foundation_slots":len(fs.get("slots",{}))})
        snap=r.conversation_snapshot()
        return {"turns":len(rows),"nonempty":sum(x["nonempty"] for x in rows),
          "unknown":sum(x["unknown"] for x in rows),
          "verified":sum(x["verification"]=="PASS" for x in rows),
          "state_turns":snap.get("turns",0),"topic":snap.get("current_topic",""),
          "foundation_events":rows[-1]["foundation_events"],"foundation_slots":rows[-1]["foundation_slots"],
          "elapsed_ms":round((time.perf_counter()-started)*1000,2),"rows":rows}
    finally:r.close()
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False,indent=2))
