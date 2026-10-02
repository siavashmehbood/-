"""Bounded observe-act-verify computer use; cognition remains the decision owner."""
from dataclasses import dataclass,asdict
from datetime import datetime
from time import perf_counter

@dataclass
class ComputerOutcome:
    goal:str; tool:str; arguments:dict; permission:str; execution:dict
    verification:dict; latency_ms:float; success:bool; timestamp:str

class ComputerUse:
    def __init__(self,runtime,max_steps=4):
        self.runtime=runtime; self.max_steps=max(1,int(max_steps))
    def execute(self,goal,tool,arguments=None,verify=None):
        arguments=dict(arguments or {}); registered=self.runtime.registry.get(tool)
        if registered is None: return self._failure(goal,tool,arguments,"unknown_tool")
        permission=registered.permission
        if not self.runtime.policy.allows(permission):
            return self._failure(goal,tool,arguments,"permission_denied",permission)
        started=perf_counter()
        try:
            result=registered.run(**arguments)
            verification=self._verify(tool,result,verify)
            success=bool(verification.get("verified"))
            execution={"ok":True,"result":result}
        except Exception as exc:
            execution={"ok":False,"error":type(exc).__name__,"detail":str(exc)[:300]}
            verification={"verified":False,"reason":"execution_failed"}
            success=False
        outcome=ComputerOutcome(str(goal),tool,arguments,permission,execution,verification,
            round((perf_counter()-started)*1000,3),success,datetime.now().isoformat(timespec="seconds"))
        self._record(outcome)
        return asdict(outcome)
    def _verify(self,tool,result,verify):
        if callable(verify):
            try:return {"verified":bool(verify(result)),"reason":"custom_verifier"}
            except Exception:return {"verified":False,"reason":"verifier_error"}
        if isinstance(result,dict):
            for key in ("exists","running","spoken"):
                if key in result:return {"verified":bool(result[key]),"reason":key}
        if tool in {"system_info","find_file","list_running_apps"}:
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
