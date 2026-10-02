"""Performance probe for Semantic Intelligence Phase 1.

Runs in repository CI only. Measures cold start, warm turn, semantic analysis,
and semantic evidence retrieval without external APIs or cloud dependencies.
"""
import json
import shutil
import tempfile
import time
from pathlib import Path

from runtime.app import IranRuntime

SRC=Path(__file__).resolve().parents[1]


def make_runtime():
    root=Path(tempfile.mkdtemp(prefix="iran_semantic_perf_"))
    shutil.copy(SRC/"config.json",root/"config.json")
    shutil.copytree(SRC/"data",root/"data")
    (root/"logs").mkdir(exist_ok=True)
    for p in (
        root/"data"/"conversation_state.json",
        root/"data"/"conversation_events.json",
        root/"data"/"context_tracker.json",
        root/"data"/"semantic-perf.db",
    ):
        p.unlink(missing_ok=True)
    cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
    cfg["memory"]["db"]="data/semantic-perf.db"
    cfg["runtime"]["event_log"]="logs/events.jsonl"
    cfg["runtime"]["goals"]="data/goals.json"
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
    started=time.perf_counter()
    runtime=IranRuntime(root)
    cold=(time.perf_counter()-started)*1000
    return runtime,cold


def run():
    r,cold=make_runtime()
    try:
        r.handle("من روی پروژه‌ای به اسم افق کار می‌کنم که برای کتاب صوتی است.")
        warm=[]
        for msg in ("سلام","حالا درباره لینوکس حرف بزنیم.","اون پروژه اسمش چی بود؟"):
            t=time.perf_counter(); r.handle(msg); warm.append((time.perf_counter()-t)*1000)

        si=r.cognitive_system.pipeline.semantic_intelligence
        slots=r.cognitive_system.pipeline.conversation_foundation.current_state().get("slots",{})
        semantic=[]
        for msg in (
            "من روی پروژه‌ای به اسم سپند کار می‌کنم.",
            "اسم پروژه قبلی چی بود؟",
            "یکی از همکارام اسمش نوید است.",
            "اسم همکارم چی بود؟",
        ):
            t=time.perf_counter(); si.analyze(msg,slots=slots,source_turn=1)
            semantic.append((time.perf_counter()-t)*1000)

        query=si.analyze("اون پروژه اسمش چی بود؟",slots=slots,source_turn=2)
        t=time.perf_counter(); evidence=si._rank_evidence(query)
        retrieval=(time.perf_counter()-t)*1000

        result={
            "cold_start_ms":round(cold,2),
            "warm_turn_ms":{"min":round(min(warm),2),"max":round(max(warm),2),
                            "avg":round(sum(warm)/len(warm),2)},
            "semantic_analysis_ms":{"min":round(min(semantic),3),"max":round(max(semantic),3),
                                    "avg":round(sum(semantic)/len(semantic),3)},
            "memory_retrieval_ms":round(retrieval,3),
            "evidence_count":len(evidence),
            "backend":si.backend_status(),
        }
        result["pass"]=(cold < 10000 and max(warm) < 5000 and
                        max(semantic) < 1000 and retrieval < 1000)
        return result
    finally:
        r.close()


if __name__=="__main__":
    result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["pass"] else 1)
