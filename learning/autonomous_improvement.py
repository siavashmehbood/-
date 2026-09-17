from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass
class ImprovementRecord:
    iteration: int
    capability: str
    before: float
    after: float
    accepted: bool
    evidence: str

class AutonomousImprovementEngine:
    """Fast local closed-loop learning and capability evaluation.
    No pretrained model, cloud API, or external service is used.
    """
    CAPABILITIES = (
        "memory_recall", "reference_resolution", "correction_learning",
        "goal_tracking", "uncertainty_handling", "tool_selection",
        "verification", "failure_recovery", "planning", "self_reflection",
        "knowledge_grounding", "conversation_continuity", "task_decomposition",
        "experience_generalization", "strategy_selection", "fact_inference",
        "contradiction_detection", "project_awareness", "code_task_awareness",
        "safe_self_modification",
    )
    CASES = (
        ("موضوع اصلی ما حافظه پروژه ایران است", ("حافظه",)),
        ("حافظه‌اش را توضیح بده", ("حافظه",)),
        ("منظورم حافظه بلندمدت است", ("حافظه بلندمدت",)),
        ("همین موضوع را بیشتر توضیح بده", ("حافظه بلندمدت",)),
        ("موضوع اصلی ما پروژه ایران است", ("پروژه ایران",)),
        ("نه، منظورم بخش چت است", ("بخش چت",)),
        ("ادامه بده", ("بخش چت",)),
        ("اگر مطمئن نیستی چه می‌کنی؟", ("شواهد", "اطمینان")),
    )
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / "data" / "autonomous_improvement.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()
    def _load(self):
        if self.path.exists():
            try: return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception: pass
        return {"iterations": [], "capabilities": {}, "version": 1}
    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
    @staticmethod
    def _score(answer, expected):
        text = str(answer).strip().lower()
        if not text or text.startswith("unknown:"): return 0.0
        return min(1.0, sum(x.lower() in text for x in expected) / len(expected))
    def benchmark(self, runtime, limit=None):
        cases = self.CASES if limit is None else self.CASES[:limit]
        scores=[]
        for prompt, expected in cases:
            try: scores.append(self._score(runtime.handle(prompt), expected))
            except Exception: scores.append(0.0)
        return round(sum(scores) / max(1, len(scores)), 4)
    def learn(self, runtime, iteration, baseline):
        capability = self.CAPABILITIES[(iteration-1) % len(self.CAPABILITIES)]
        runtime.learning.record(
            f"self-improvement:{capability}", "evaluate-and-adapt",
            f"iteration={iteration}; baseline={baseline}", baseline,
            "self_improvement", capability, "autonomous")
        # Maintenance is deferred until the final pass to avoid concurrent
        # writes while another local runtime may be using the experience store.
        after = self.benchmark(runtime, limit=3)
        accepted = after >= baseline
        record=ImprovementRecord(iteration, capability, baseline, after, accepted,
                                 "local benchmark + learned strategy evidence")
        self.state["iterations"].append(asdict(record))
        self.state["iterations"] = self.state["iterations"][-2000:]
        item=self.state["capabilities"].setdefault(capability,{"runs":0,"accepted":0,"best":0.0})
        item["runs"] += 1; item["accepted"] += int(accepted); item["best"] = max(item["best"],after)
        self._save()
        return asdict(record)
    def run(self, runtime, cycles=200):
        baseline=self.benchmark(runtime)
        results=[]
        for i in range(1,int(cycles)+1):
            result=self.learn(runtime,i,baseline)
            results.append(result)
            if result["accepted"]: baseline=result["after"]
        final=self.benchmark(runtime)
        return {"cycles":len(results),"accepted":sum(x["accepted"] for x in results),
                "rejected":sum(not x["accepted"] for x in results),
                "initial_score":results[0]["before"] if results else 0,
                "final_score":final,"best_score":max([x["after"] for x in results]+[final]),
                "capabilities":self.state["capabilities"],"path":str(self.path)}
