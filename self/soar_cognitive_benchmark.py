"""Performance evidence for IRAN Phase 2 / Soar cognitive foundation."""
import json
import shutil
import tempfile
import time
from pathlib import Path

from runtime.app import IranRuntime

SRC=Path(__file__).resolve().parents[1]


def make_runtime():
    root=Path(tempfile.mkdtemp(prefix="iran_soar_perf_"))
    shutil.copy(SRC/"config.json",root/"config.json")
    shutil.copytree(SRC/"data",root/"data")
    shutil.copytree(SRC/"cognitive",root/"cognitive")
    (root/"logs").mkdir(exist_ok=True)
    for name in (
        "conversation_state.json","conversation_events.json","context_tracker.json",
        "soar-perf.db","soar_epmem.sqlite","learning_proposals.json"
    ):
        (root/"data"/name).unlink(missing_ok=True)
    cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
    cfg["memory"]["db"]="data/soar-perf.db"
    cfg["runtime"]["event_log"]="logs/events.jsonl"
    cfg["runtime"]["goals"]="data/goals.json"
    (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
    started=time.perf_counter()
    runtime=IranRuntime(root)
    runtime_ms=(time.perf_counter()-started)*1000
    return runtime,runtime_ms


def run():
    r,runtime_ms=make_runtime()
    try:
        engine=r.cognitive_system.cognitive_engine
        status=engine.status()
        si=r.cognitive_system.pipeline.semantic_intelligence
        state=r.dialogue.state

        # Seed structured semantic facts and one prior cognitive episode.
        r.handle("من روی پروژه‌ای به اسم راهکار کار می‌کنم که برای بررسی اسناد است.")
        slots=r.cognitive_system.pipeline.conversation_foundation.current_state().get("slots",{})

        cycle_times=[]
        wm_sync_times=[]
        semantic_retrieval_times=[]
        episodic_retrieval_times=[]
        multi_step_times=[]
        selected=[]

        for idx,msg in enumerate((
            "اسم پروژه قبلی چی بود؟",
            "پروژه راهکار برای چی بود؟",
            "اطلاعات کافی ندارم؛ چه کار شناختی باید انجام شود؟",
            "یک هدف چندمرحله‌ای برای بررسی پروژه بساز",
        ),1):
            turn=si.analyze(msg,slots=slots,source_turn=idx+2)
            goal=engine._goal(turn,state,{"intent":"planning","goal":msg})
            operators=engine._operators(turn,{"intent":"planning","goal":msg})

            t=time.perf_counter()
            semantic_rows,episode_rows=engine._memory_retrievals(goal,turn)
            retrieval_total=(time.perf_counter()-t)*1000
            semantic_retrieval_times.append(retrieval_total)
            episodic_retrieval_times.append(retrieval_total)

            t=time.perf_counter()
            engine._populate_working_memory(turn,state,goal,operators,semantic_rows,episode_rows,False)
            wm_sync_times.append((time.perf_counter()-t)*1000)

            t=time.perf_counter()
            cycle=engine.cycle(turn,state,parsed={"intent":"planning","goal":msg})
            cycle_times.append((time.perf_counter()-t)*1000)
            multi_step_times.append(cycle.elapsed_ms)
            selected.append(cycle.selected_operator)

        result={
            "runtime_init_ms":round(runtime_ms,2),
            "soar_init_ms":round(float(status.get("init_elapsed_ms",0.0)),3),
            "cognitive_cycle_ms":{
                "min":round(min(cycle_times),3),"max":round(max(cycle_times),3),
                "avg":round(sum(cycle_times)/len(cycle_times),3),
            },
            "working_memory_sync_ms":{
                "min":round(min(wm_sync_times),3),"max":round(max(wm_sync_times),3),
                "avg":round(sum(wm_sync_times)/len(wm_sync_times),3),
            },
            "semantic_memory_retrieval_ms":{
                "max":round(max(semantic_retrieval_times),3),
                "avg":round(sum(semantic_retrieval_times)/len(semantic_retrieval_times),3),
            },
            "episodic_retrieval_ms":{
                "max":round(max(episodic_retrieval_times),3),
                "avg":round(sum(episodic_retrieval_times)/len(episodic_retrieval_times),3),
            },
            "multi_step_task_ms":{
                "max":round(max(multi_step_times),3),
                "avg":round(sum(multi_step_times)/len(multi_step_times),3),
            },
            "selected_operators":selected,
            "limits":status.get("limits",{}),
            "real_soar":status.get("real_soar",False),
            "backend":status.get("backend",""),
        }
        result["pass"]=bool(
            result["real_soar"] and
            result["soar_init_ms"] < 5000 and
            result["cognitive_cycle_ms"]["max"] < 1500 and
            result["working_memory_sync_ms"]["max"] < 500 and
            result["semantic_memory_retrieval_ms"]["max"] < 500 and
            result["episodic_retrieval_ms"]["max"] < 500 and
            result["multi_step_task_ms"]["max"] < 1500
        )
        return result
    finally:
        r.close()


if __name__=="__main__":
    result=run()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["pass"] else 1)
