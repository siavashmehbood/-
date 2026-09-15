"""Deterministic Persian conversation benchmark for IRAN."""
import json, shutil, tempfile
from pathlib import Path
from runtime.app import IranRuntime

def u(h): return ''.join(chr(int(x,16)) for x in h.split())
P=u("067e 0627 06cc 062a 0648 0646")
H=u("062d 0627 0641 0638 0647")
PROJ=u("067e 0631 0648 0698 0647")
PROG=u("0628 0631 0646 0627 0645 0647 200c 0646 0648 06cc 0633 06cc")
ABOUT=u("062f 0631 0628 0627 0631 0647 200c 06cc 062e 0648 062f 0645")
CATEGORIES=("intent_accuracy","reference_accuracy","context_retention","answer_relevance","evidence_grounding","unknown_honesty","correction_handling","topic_switching","topic_restoration","multi_intent","memory_recall","multi_turn_consistency")
class PersianConversationBenchmark:
    CATEGORIES=CATEGORIES
    def _root(self):
        src=Path(__file__).resolve().parents[1]; tmp=Path(tempfile.mkdtemp(prefix="iran_pcb_"))
        shutil.copy(src/"config.json",tmp/"config.json"); shutil.copytree(src/"data",tmp/"data"); (tmp/"logs").mkdir()
        state=tmp/"data"/"conversation_state.json"; state.unlink(missing_ok=True)
        cfg=json.loads((tmp/"config.json").read_text(encoding="utf-8-sig")); cfg["memory"]["db"]="data/benchmark.db"; cfg["runtime"]["event_log"]="logs/benchmark.jsonl"; cfg["runtime"]["goals"]="data/goals.json"
        (tmp/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8"); return tmp
    def _cases(self):
        cases=[]
        def add(cat,msgs,expected):
            for _ in range(10): cases.append((cat,msgs,expected))
        add("intent_accuracy",[u("067e 0627 06cc 062a 062e 062a 0020 0627 06cc 0631 0627 0646 0020 06a9 062c 0627 0633 062a 061f")],u("062a 0647 0631 0627 0646"))
        add("reference_accuracy",[P+u("0020 0686 06cc 0647 061f"),u("0647 0645 0648 0646 0020 0642 0628 0644 06cc 0020 0631 0648 0020 0627 062f 0627 0645 0647 0020 0628 062f 0647")],P)
        add("context_retention",[P+u("0020 0686 06cc 0647 061f"),u("0686 0631 0627 0020 0645 062d 0628 0648 0628 0647 061f")],P)
        add("answer_relevance",[P+u("0020 0686 06cc 0647 061f")],PROG)
        add("evidence_grounding",[u("067e 0627 06cc 062a 062e 062a 0020 0627 06cc 0631 0627 0646 0020 06a9 062c 0627 0633 062a 061f")],u("062a 0647 0631 0627 0646"))
        add("unknown_honesty",[u("062f 0645 0627 06cc 0020 062f 0642 06cc 0642 0020 0647 0633 062a 0647 0020 0645 0634 062a 0631 06cc 0020 062f 0631 0020 0633 0627 0644 0020 06f1 06f4 06f2 06f0 0020 0686 0646 062f 0020 0627 0633 062a 061f")],"UNKNOWN")
        add("correction_handling",[P+u("0020 0686 06cc 0647 061f"),u("0646 0647 060c 0020 0645 0646 0638 0648 0631 0645 0020 062d 0627 0641 0638 0647 0020 0628 0648 062f") ,u("0647 0645 0648 0646 0020 0642 0628 0644 06cc 0020 0631 0648 0020 0627 062f 0627 0645 0647 0020 0628 062f 0647")],H)
        add("topic_switching",[P+u("0020 0686 06cc 0647 061f"),H+u("0020 0686 06cc 0647 061f")],H)
        add("topic_restoration",[P+u("0020 0686 06cc 0647 061f"),H+u("0020 0686 06cc 0647 061f"),u("0645 0648 0636 0648 0639 0020 0642 0628 0644 06cc 0020 0631 0648 0020 0627 062f 0627 0645 0647 0020 0628 062f 0647")],P)
        add("multi_intent",[P+u("0020 0686 06cc 0647 0020 0648 0020 0686 0631 0627 0020 0645 062d 0628 0648 0628 0647 0020 0648 0020 0628 0631 0627 06cc 0020 067e 0631 0648 0698 0647 0020 0645 0646 0020 0686 0647 0020 0641 0627 06cc 062f 0647 200c 0627 06cc 0020 062f 0627 0631 0647 061f")],u("06f3 0029"))
        add("memory_recall",[u("0645 0646 0020")+PROG+u("0020 0631 0627 0020 062f 0648 0633 062a 0020 062f 0627 0631 0645"),u("0645 0646 0020 0686 0647 0020 0686 06cc 0020 06af 0641 062a 0645 061f")],PROG)
        add("multi_turn_consistency",[P+u("0020 0686 06cc 0647 061f"),u("0628 0631 0627 06cc 0020 067e 0631 0648 0698 0647 0020 0645 0646 0020 062e 0648 0628 0647 061f"),u("0647 0645 0648 0646 0020 0642 0628 0644 06cc 0020 0631 0648 0020 0627 062f 0627 0645 0647 0020 0628 062f 0647")],P)
        return cases
    def run(self):
        cases=self._cases(); passed=0; details=[]
        for category,messages,expected in cases:
            tmp=self._root(); runtime=None
            try:
                runtime=IranRuntime(tmp); answer=""
                for message in messages: answer=runtime.handle(message)
                ok=expected in answer; details.append({"category":category,"ok":bool(ok),"answer":answer[:240]}); passed+=int(bool(ok))
            except Exception as exc: details.append({"category":category,"ok":False,"error":type(exc).__name__})
            finally:
                try:
                    if runtime: runtime.close()
                finally: shutil.rmtree(tmp,ignore_errors=True)
        by_category={c:round(100*sum(1 for d in details if d["category"]==c and d["ok"])/10,2) for c in CATEGORIES}; score=round(100*passed/len(cases),2)
        return {"cases":len(cases),"passed":passed,"score":score,"by_category":by_category,"pass":passed==len(cases),"details":details}
if __name__=="__main__": print(json.dumps(PersianConversationBenchmark().run(),ensure_ascii=False,indent=2))
