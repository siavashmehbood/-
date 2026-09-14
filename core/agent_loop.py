from dataclasses import dataclass,field
import time
@dataclass
class LoopResult:
    goal:str; status:str; answer:str=''; attempts:int=0; score:float=0.0; observations:list=field(default_factory=list)
class AgentLoop:
    def __init__(self,orchestrator,max_attempts=3): self.orchestrator=orchestrator; self.max_attempts=max(1,int(max_attempts))
    def run(self,goal):
        goal=str(goal).strip()
        if not goal:return LoopResult('','rejected')
        obs=[]; self.orchestrator.events.emit('agent_loop_started',{'goal':goal})
        for attempt in range(1,self.max_attempts+1):
            started=time.perf_counter()
            try:
                answer=self.orchestrator.handle(goal)
                scorer=getattr(self.orchestrator,'evaluator',None)
                score=scorer.score(goal,answer) if scorer else (0.7 if answer else 0)
                obs.append({'attempt':attempt,'ok':True,'score':score,'answer':answer})
                if score>=0.45:
                    self.orchestrator.events.emit('agent_loop_completed',{'goal':goal,'attempts':attempt,'score':score}); return LoopResult(goal,'completed',answer,attempt,score,obs)
            except Exception as exc: obs.append({'attempt':attempt,'ok':False,'error':str(exc)})
            self.orchestrator.metrics.record('retry',time.perf_counter()-started)
            self.orchestrator.events.emit('agent_loop_retry',{'goal':goal,'attempt':attempt})
        answer=obs[-1].get('answer','') if obs else ''
        return LoopResult(goal,'failed',answer or 'اجرای هدف ناموفق بود.',self.max_attempts,0,obs)
