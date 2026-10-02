"""A/B benchmark: canonical IRAN with foundation disabled vs enabled.

Both arms use the same current code and unseen corpus. The only variable is the
RasaFoundationAdapter state/event layer, so differences measure foundation cost
and state value without introducing a second decision owner.
"""
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

class NullFoundation:
    """No-op A/B control. Deliberately exposes no decision/action API."""
    def ingest(self,*a,**k): return {}
    def record_outcome(self,*a,**k): return None
    def save(self): return None
    def current_state(self): return {"slots":{},"latest_message":{},"active_loop":"","previous_action":"","events":[]}

def runtime(label):
    src=Path(__file__).resolve().parents[1]
    root=Path(tempfile.mkdtemp(prefix=f"iran_rasa_ab_{label}_"))
    shutil.copy(src/"config.json",root/"config.json"); shutil.copytree(src/"data",root/"data"); (root/"logs").mkdir()
    (root/"data"/"conversation_state.json").unlink(missing_ok=True)
    (root/"data"/"conversation_events.json").unlink(missing_ok=True)
    cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
    cfg["memory"]["db"]="data/ab.db"; cfg["runtime"]["event_log"]="logs/ab.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
    return IranRuntime(root)

def run_arm(enabled=True):
    r=runtime("foundation" if enabled else "current")
    if not enabled:
        r.cognitive_system.pipeline.conversation_foundation=NullFoundation()
    rows=[]; started=time.perf_counter()
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

def run():
    current=run_arm(False)
    foundation=run_arm(True)
    stable_keys=("turns","nonempty","unknown","verified","state_turns","topic")
    regressions={k:{"current":current[k],"foundation":foundation[k]}
                 for k in stable_keys if current[k]!=foundation[k]}
    overhead=round(foundation["elapsed_ms"]-current["elapsed_ms"],2)
    ratio=round(foundation["elapsed_ms"]/max(current["elapsed_ms"],0.001),3)
    return {
      "current":current,
      "foundation":foundation,
      "regressions":regressions,
      "performance":{"overhead_ms":overhead,"ratio":ratio},
      "one_brain":True,
      "pass":not regressions and foundation["foundation_events"]>=80,
    }

if __name__=="__main__":
    result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["pass"] else 1)
