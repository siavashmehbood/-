"""Bounded observe-act-verify coordinator. CognitiveSystem remains the sole decision owner."""
from dataclasses import dataclass,asdict,field
from datetime import datetime
from time import perf_counter
import json,hashlib,threading

@dataclass
class ComputerOutcome:
    goal:str; tool:str; arguments:dict; permission:str; execution:dict
    verification:dict; latency_ms:float; success:bool; timestamp:str

@dataclass
class ComputerTaskEpisode:
    goal:str; observations:list=field(default_factory=list); actions:list=field(default_factory=list)
    failures:list=field(default_factory=list); recoveries:list=field(default_factory=list)
    final_outcome:str="running"; step_count:int=0; duration_ms:float=0.0
    started_at:str=field(default_factory=lambda:datetime.now().isoformat(timespec="seconds"))

class ComputerUse:
    def __init__(self,runtime,max_steps=8):
        self.runtime=runtime; self.max_steps=max(1,int(max_steps)); self._cancel=threading.Event()
    def cancel(self): self._cancel.set()
    def reset_cancel(self): self._cancel.clear()
    def execute(self,goal,tool,arguments=None,verify=None):
        arguments=dict(arguments or {}); registered=self.runtime.registry.get(tool)
        if registered is None:return self._failure(goal,tool,arguments,"unknown_tool")
        permission=registered.permission
        if not self.runtime.policy.allows(permission):return self._failure(goal,tool,arguments,"permission_denied",permission)
        started=perf_counter()
        try:
            result=registered.run(**arguments); verification=self._verify(tool,result,verify)
            success=bool(verification.get("verified")); execution={"ok":True,"result":result}
        except Exception as exc:
            execution={"ok":False,"error":type(exc).__name__,"detail":str(exc)[:300]}
            verification={"verified":False,"reason":"execution_failed"}; success=False
        outcome=ComputerOutcome(str(goal),tool,arguments,permission,execution,verification,
            round((perf_counter()-started)*1000,3),success,datetime.now().isoformat(timespec="seconds"))
        self._record(outcome); return asdict(outcome)
    def run(self,goal,steps,timeout_seconds=30):
        started=perf_counter(); reports=[]
        for step in list(steps or [])[:self.max_steps]:
            if self._cancel.is_set():return {"success":False,"stop_reason":"user_cancel","steps":reports}
            if perf_counter()-started>float(timeout_seconds):return {"success":False,"stop_reason":"timeout","steps":reports}
            report=self.execute(goal,step["tool"],step.get("arguments",{}),step.get("verify")); reports.append(report)
            if not report.get("success"):return {"success":False,"stop_reason":"verification_failure","steps":reports}
        truncated=len(list(steps or []))>self.max_steps
        return {"success":bool(reports) and not truncated,"stop_reason":"max_steps" if truncated else "goal_complete","steps":reports}
    def adaptive_run(self,goal,observe,decide,timeout_seconds=45,max_retries_per_action=2,max_consecutive_failures=3):
        """Step-driven loop: observe -> canonical decide -> execute -> observe -> verify -> replan."""
        self.reset_cancel(); started=perf_counter(); ep=ComputerTaskEpisode(str(goal)); repeated={}
        last_verification=None
        for index in range(self.max_steps):
            if self._cancel.is_set():return self._finish(ep,started,"user_cancel",False)
            if perf_counter()-started>float(timeout_seconds):return self._finish(ep,started,"timeout",False)
            before=observe(); before_dict=before.to_dict() if hasattr(before,"to_dict") else dict(before)
            ep.observations.append(before_dict)
            decision=decide(str(goal),before_dict,list(ep.actions),last_verification,self.max_steps-index)
            if not decision:return self._finish(ep,started,"safe_stop_no_decision",False)
            if decision.get("status")=="goal_complete":return self._finish(ep,started,"goal_complete",True)
            action={"tool":decision.get("tool"),"arguments":dict(decision.get("arguments") or {}),
                    "expected":decision.get("expected"),"confidence":decision.get("confidence",0.0)}
            sig=before_dict.get("signature",""); key=(sig,action["tool"],json.dumps(action["arguments"],sort_keys=True,default=str))
            repeated[key]=repeated.get(key,0)+1
            if repeated[key]>max_retries_per_action:return self._finish(ep,started,"loop_detected",False)
            report=self.execute(goal,action["tool"],action["arguments"],decision.get("verify")); action["outcome"]=report
            after=observe(); after_dict=after.to_dict() if hasattr(after,"to_dict") else dict(after); ep.observations.append(after_dict)
            evidence=self._verify_transition(decision,report,before_dict,after_dict); action["transition_verification"]=evidence
            ep.actions.append(action); ep.step_count=len(ep.actions); last_verification=evidence
            if not evidence["verified"]:
                ep.failures.append({"step":index+1,"action":action,"evidence":evidence})
                if len(ep.failures)>=max_consecutive_failures and all(not x["evidence"]["verified"] for x in ep.failures[-max_consecutive_failures:]):
                    return self._finish(ep,started,"consecutive_failures",False)
            elif ep.failures:ep.recoveries.append({"step":index+1,"action":action["tool"]})
        return self._finish(ep,started,"max_steps",False)
    def _verify_transition(self,decision,report,before,after):
        if not report.get("success"):return {"verified":False,"reason":report.get("verification",{}).get("reason","action_failed")}
        strategy=decision.get("verification") or {}
        kind=strategy.get("type","state_change")
        if kind=="file_exists":
            from pathlib import Path
            return {"verified":Path(str(strategy.get("path",""))).exists(),"reason":"file_exists"}
        if kind=="window_title":
            title=str((after.get("active_window") or {}).get("title","")).casefold()
            return {"verified":str(strategy.get("contains","")).casefold() in title,"reason":"window_title"}
        if kind=="element_present":
            label=str(strategy.get("label","")).casefold()
            return {"verified":any(label in str(e.get("label","")).casefold() for e in after.get("elements",[])),"reason":"element_present"}
        changed=before.get("signature")!=after.get("signature")
        return {"verified":bool(changed or report.get("verification",{}).get("verified")),"reason":"state_or_tool_evidence"}
    def _finish(self,ep,started,reason,success):
        ep.final_outcome=reason; ep.duration_ms=round((perf_counter()-started)*1000,3)
        payload=asdict(ep); payload["success"]=bool(success)
        try:self.runtime.events.emit("computer_task_episode",payload)
        except Exception:pass
        if not success:
            try:self.runtime.cognitive_system.growth.evaluate_failure("autonomous_computer_use",ep.goal,
                "goal complete with evidence",reason,"computer task "+reason,.9,[str(payload)],["ComputerUse","ScreenPerception"])
            except Exception:pass
        return payload
    def _verify(self,tool,result,verify):
        if callable(verify):
            try:return {"verified":bool(verify(result)),"reason":"custom_verifier"}
            except Exception:return {"verified":False,"reason":"verifier_error"}
        if isinstance(result,dict):
            for key in ("exists","running","spoken","focused","written","opened"):
                if key in result:return {"verified":bool(result[key]),"reason":key}
        if tool in {"system_info","find_file","list_running_apps","list_windows","active_window","clipboard_read"}:
            return {"verified":result is not None,"reason":"observable_result"}
        return {"verified":False,"reason":"no_verifier"}
    def _failure(self,goal,tool,args,reason,permission="unknown"):
        outcome=ComputerOutcome(str(goal),str(tool),args,permission,{"ok":False,"error":reason},
            {"verified":False,"reason":reason},0.0,False,datetime.now().isoformat(timespec="seconds"))
        self._record(outcome); return asdict(outcome)
    def _record(self,outcome):
        payload=asdict(outcome)
        try:self.runtime.events.emit("computer_action",payload)
        except Exception:pass
        try:self.runtime.input_fabric.ingest(str(payload),source="execution",input_type="execution_result",
            provenance={"tool":outcome.tool},confidence=1.0 if outcome.success else .2,create_goal=False)
        except Exception:pass
        if not outcome.success:
            try:self.runtime.cognitive_system.growth.evaluate_failure("computer_use",outcome.goal,
                "verified successful action",str(outcome.execution),outcome.verification.get("reason","failure"),
                .9,[str(payload)],["ComputerUse",outcome.tool])
            except Exception:pass
