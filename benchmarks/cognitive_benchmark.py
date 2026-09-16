"""100 deterministic model-free cognitive architecture scenarios."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

from core.nars_reasoner import NarsInspiredReasoner
from core.atomspace_graph import AtomSpace
from core.working_memory import SymbolicWorkingMemory
from core.cognitive_controller import GlobalWorkspace, ProceduralLearner, CognitiveController
from core.goal_stack import GoalStack
from core.decision_cycle import DecisionCycle
from core.production_rules import ProductionRule
from core.causal_reasoning import CausalGraph
from core.analogical_reasoning import AnalogicalReasoner
from core.metacognition import MetacognitiveMonitor
from core.virtual_world import VirtualWorld, WorldEvent
from language_intelligence import PersianIntelligence

@dataclass
class Case:
    id:int
    category:str
    name:str

class CognitiveBenchmark:
    CATEGORIES=("knowledge","reasoning","contradiction","memory","attention",
                 "planning","language","learning","recovery","autonomy")

    def __init__(self):
        self.cases=[Case(i,cat,f"{cat}_{i}") for cat in self.CATEGORIES for i in range(1,11)]

    def _knowledge(self,i):
        r=NarsInspiredReasoner(); s=f"entity_{i}"; v=f"value_{i}"
        r.observe(s,"property",v,.95,"benchmark")
        a=r.ask(s,"property")
        return a.answer==v and a.confidence>.9,a

    def _reasoning(self,i):
        r=NarsInspiredReasoner(); a=f"A{i}"; b=f"B{i}"; c=f"C{i}"
        r.observe(a,"rel",b,.9,"benchmark"); r.observe(b,"rel",c,.9,"benchmark")
        d=r.derive(a,2); return any(x.value==c for x in d),d

    def _contradiction(self,i):
        r=NarsInspiredReasoner(); s=f"subject_{i}"
        r.observe(s,"state","A",.8,"source_a"); r.observe(s,"state","B",.75,"source_b")
        rows=r.competing(s,"state")
        return len(rows)==2 and {x.value for x in rows}=={"A","B"},rows

    def _memory(self,i):
        m=SymbolicWorkingMemory(capacity=20); key=f"memory token {i}"
        m.add(key,salience=.9,tags=["benchmark"]); rows=m.retrieve(key,limit=1)
        return bool(rows and rows[0].content==key),rows

    def _attention(self,i):
        w=GlobalWorkspace(capacity=10,broadcast_limit=2)
        target=f"critical item {i}"; w.add(target,"knowledge",.95,.95); w.add("noise","memory",.1,.1)
        rows=w.attend("critical item"); return bool(rows and rows[0].content==target),rows

    def _planning(self,i):
        stack=GoalStack(max_depth=10); root=f"goal {i}"; child=f"subgoal {i}"
        stack.push(root); stack.push(child); ok=stack.current()==child; stack.pop(); ok=ok and stack.current()==root
        rule=ProductionRule(f"rule_{i}",conditions=["intent={intent}"],action="respond",priority=.9,confidence=.9)
        match=rule.match({"intent":"question"}); return ok and match is not None,(stack.snapshot(),match)

    def _language(self,i):
        p=PersianIntelligence(); text=f"برای پروژه {i} یک برنامه مرحله‌ای بساز و بعد نتیجه را بررسی کن"
        result=p.analyze(text,{})
        ok=bool(result.get("intent")) and isinstance(result.get("constraints"),list)
        return ok,result

    def _learning(self,i):
        import tempfile
        with tempfile.TemporaryDirectory(prefix="iran-learn-") as td:
            learner=ProceduralLearner(Path(td)/"procedures.json")
            p=learner.record(f"intent_{i}",["inspect","act","verify"],True,.95)
            learner.record(f"intent_{i}",["guess"],False,.1)
            restored=ProceduralLearner(Path(td)/"procedures.json")
            best=restored.best(f"intent_{i}")
            return bool(best and best.steps==["inspect","act","verify"] and best.value>.5),best

    def _recovery(self,i):
        graph=CausalGraph(); cause=f"failure_{i}"; fix=f"recovery_{i}"; graph.add(cause,"requires",fix)
        analog=AnalogicalReasoner(); result=analog.compare({"goal":"restore","steps":["inspect","fix"]},{"goal":"restore","steps":["inspect","fix","verify"]})
        meta=MetacognitiveMonitor().evaluate([{"support":True,"confidence":.9}],ambiguity=.0)
        return bool(graph.path(cause,fix)) and result.score>0 and meta.confidence>.5,(graph.snapshot(),result,meta)

    def _autonomy(self,i):
        world=VirtualWorld(state={"system":"degraded","queue":i%3,"resource":5})
        history=[]
        for cycle in range(1,10):
            before=world.observe(); legal=world.legal_actions()
            if "restore" in legal: action="restore"
            elif "process_queue" in legal: action="process_queue"
            else: action="inspect"
            result=world.act(action); history.append((before,action,result))
            if world.goal_satisfied("restore system"): break
        safe=all(x[1] in x[0] if False else x[2]["success"] for x in history)
        return world.goal_satisfied("restore system") and safe,history

    def _run_case(self,case):
        fn=getattr(self,f"_{case.category}"); return fn((case.id-1)%10+1)

    def run(self):
        results=[]
        for case in self.cases:
            try:
                passed,detail=self._run_case(case); error=""
            except Exception as exc:
                passed=False; detail=""; error=f"{type(exc).__name__}: {exc}"
            results.append({"id":case.id,"category":case.category,"name":case.name,
                            "passed":bool(passed),"detail":str(detail)[:1000],"error":error})
        passed=sum(x["passed"] for x in results); failures=[x for x in results if not x["passed"]]
        categories={}
        for cat in self.CATEGORIES:
            rows=[x for x in results if x["category"]==cat]
            categories[cat]={"total":10,"passed":sum(x["passed"] for x in rows),"failed":sum(not x["passed"] for x in rows)}
        return {"total":100,"passed":passed,"failed":len(failures),"pass_rate":round(passed/100,4),
                "success":not failures,"categories":categories,"failures":failures,"results":results}


def run_and_write(output=None):
    report=CognitiveBenchmark().run()
    target=Path(output or Path(__file__).resolve().parents[1]/"data"/"cognitive_benchmark_report.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

if __name__=="__main__":
    report=run_and_write()
    print(json.dumps({"total":report["total"],"passed":report["passed"],"failed":report["failed"],
                      "pass_rate":report["pass_rate"],"success":report["success"],"categories":report["categories"]},
                     ensure_ascii=False,indent=2))

# API-accurate adapters discovered by the first benchmark run.
def _memory_fixed(self,i):
    m=SymbolicWorkingMemory(capacity=20); key=f"memory token {i}"
    m.add(key,salience=.9,tags=["benchmark"]); rows=m.recall(key,limit=1)
    return bool(rows and rows[0][1]==key),rows

def _planning_fixed(self,i):
    stack=GoalStack(max_depth=10); root=f"goal {i}"; child=f"subgoal {i}"
    stack.push(root); stack.push(child); ok=stack.current()==child; stack.pop(); ok=ok and stack.current()==root
    from core.production_rules import ProductionSystem
    system=ProductionSystem(); system.add(f"rule_{i}",["intent={intent}"],"respond",priority=9,confidence=.9)
    match=system.match(["intent=question"]); return ok and bool(match),match

def _recovery_fixed(self,i):
    graph=CausalGraph(); cause=f"failure_{i}"; fix=f"recovery_{i}"; graph.add(cause,fix)
    analog=AnalogicalReasoner(); result=analog.compare({"goal":"restore","steps":["inspect","fix"]},{"goal":"restore","steps":["inspect","fix","verify"]})
    meta=MetacognitiveMonitor().evaluate([{"support":True,"confidence":.9}],ambiguity=.0)
    return bool(graph.path(cause,fix)) and result.score>0 and meta.confidence>.5,(graph.snapshot(),result,meta)

CognitiveBenchmark._memory=_memory_fixed
CognitiveBenchmark._planning=_planning_fixed
CognitiveBenchmark._recovery=_recovery_fixed

# Re-run entry point after all compatibility adapters are installed.
if __name__=="__main__":
    report=run_and_write()
    print(json.dumps({"total":report["total"],"passed":report["passed"],"failed":report["failed"],
                      "pass_rate":report["pass_rate"],"success":report["success"],"categories":report["categories"]},
                     ensure_ascii=False,indent=2))


def _planning_fixed_v2(self,i):
    stack=GoalStack(max_depth=10); root=f"goal {i}"; child=f"subgoal {i}"
    stack.push(root); stack.push(child); ok=stack.current().name==child; stack.pop(); ok=ok and stack.current().name==root
    from core.production_rules import ProductionSystem
    system=ProductionSystem(); system.add(f"rule_{i}",["intent={intent}"],"respond",priority=9,confidence=.9)
    match=system.match(["intent=question"]); return ok and bool(match),match

def _recovery_fixed_v2(self,i):
    graph=CausalGraph(); cause=f"failure_{i}"; fix=f"recovery_{i}"; graph.add(cause,fix)
    analog=AnalogicalReasoner(); result=analog.compare({"goal":"restore","steps":["inspect","fix"]},{"goal":"restore","steps":["inspect","fix","verify"]})
    meta=MetacognitiveMonitor().assess(.9,evidence_count=2)
    return bool(graph.path(cause,fix)) and result.score>0 and meta.confidence>.5,(graph.snapshot(),result,meta)

CognitiveBenchmark._planning=_planning_fixed_v2
CognitiveBenchmark._recovery=_recovery_fixed_v2
