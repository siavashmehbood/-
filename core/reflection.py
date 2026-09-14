from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Reflection:
    goal:str; outcome:str; score:float; lessons:list[str]=field(default_factory=list)
    uncertainties:list[str]=field(default_factory=list); next_steps:list[str]=field(default_factory=list)
    timestamp:str=''

class ReflectionEngine:
    """Post-action metacognition: summarize outcome, uncertainty and next experiment."""
    def reflect(self,goal,outcome,score,observations=None):
        obs=observations or []; lessons=[]; uncertainties=[]
        if score>=.8: lessons.append('strategy produced a strong local result')
        elif score>=.55: lessons.append('result is usable but evidence should be strengthened')
        else: lessons.append('strategy needs revision before repetition')
        if not obs: uncertainties.append('limited observation evidence')
        if score<.7: uncertainties.append('outcome quality below target')
        next_steps=['store experience','update strategy statistics']
        if score<.55: next_steps += ['inspect root cause','try a different plan']
        return Reflection(str(goal),str(outcome)[:1000],float(score),lessons,uncertainties,next_steps,datetime.now().isoformat(timespec='seconds'))


    def post_action(self,goal,planned,actual,score,expected=None):
        """Compare expectation with observed result and generate a reusable lesson."""
        delta=None
        if expected is not None:
            delta=float(score)-float(expected)
        lessons=[];uncertainties=[]
        if delta is not None and delta>=.15: lessons.append('outcome exceeded expectation; strengthen this strategy prior')
        elif delta is not None and delta<=-.15: lessons.append('outcome underperformed expectation; reduce confidence and investigate cause')
        else: lessons.append('outcome was broadly consistent with expectation')
        if score<.5: uncertainties.append('observed result is weak')
        if planned!=actual: lessons.append('selected action differed from planned action; preserve the deviation as evidence')
        return Reflection(str(goal),str(actual)[:1000],float(score),lessons,uncertainties,
                          ['store experience','update prediction calibration','reassess next action'],datetime.now().isoformat(timespec='seconds'))

    def compare_runs(self,runs):
        rows=list(runs or [])
        if not rows:return {'best':None,'trend':0.0,'count':0}
        scores=[float(x.get('score',0)) for x in rows];return {'best':max(rows,key=lambda x:float(x.get('score',0))),
                'trend':round(scores[-1]-scores[0],3),'count':len(rows)}
