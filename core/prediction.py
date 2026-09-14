from dataclasses import dataclass,asdict
from collections import defaultdict
import json
from pathlib import Path

@dataclass
class Prediction:
    action:str; expected:str; risk:float; confidence:float; utility:float=0.0
    evidence:int=0; reversibility:float=.5; alternatives:list=None

class PredictionEngine:
    """Local adaptive predictor with empirical calibration, transitions and counterfactual ranking."""
    def __init__(self,path=None):
        self.path=Path(path) if path else None; self.history=[]; self.stats=defaultdict(lambda:[0.0,0]); self.transitions=defaultdict(lambda:defaultdict(int)); self._load()
    def _load(self):
        if not self.path or not self.path.exists(): return
        try:
            d=json.loads(self.path.read_text(encoding='utf-8')); self.history=d.get('history',[])[-5000:]
            for k,v in d.get('stats',{}).items(): self.stats[k]=[float(v[0]),int(v[1])]
            self.transitions=defaultdict(lambda:defaultdict(int),{k:defaultdict(int,v) for k,v in d.get('transitions',{}).items()})
        except Exception: pass
    def _save(self):
        if not self.path:return
        self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'history':self.history[-5000:],'stats':dict(self.stats),'transitions':{k:dict(v) for k,v in self.transitions.items()}},ensure_ascii=False),encoding='utf-8');tmp.replace(self.path)
    def _risk(self,text):
        t=str(text).lower(); risk=.10
        if any(x in t for x in ('حذف','پاک','deploy','انتشار','نوشتن','write','فرمت','تغییر اساسی')):risk=.72
        elif any(x in t for x in ('اجرا','run','ساخت','پیاده','تغییر')):risk=.38
        elif any(x in t for x in ('بررسی','مشاهده','خواندن','inspect','retrieve','شواهد')):risk=.06
        return risk
    def predict(self,actions,context=None,state=''):
        results=[]
        for action in actions:
            key=str(action).strip().lower(); risk=self._risk(key); total_score,total=self.stats[key]
            empirical=total_score/total if total else .5; prior=.62 if any(x in key for x in ('understand','inspect','evidence','بررسی','شواهد')) else .5
            confidence=max(.12,min(.98,.38*(1-risk)+.37*empirical+.15*prior+.10*min(1,total/12)))
            reversibility=.92 if risk<.2 else .55 if risk<.5 else .18
            utility=confidence*(1-risk)*(0.55+0.45*reversibility)
            expected='کم‌ریسک و برگشت‌پذیر' if risk<.2 else 'قابل انجام با آزمون' if risk<.5 else 'پرریسک؛ ابتدا شبیه‌سازی/پشتیبان'
            alternatives=['بررسی شواهد','اجرای کم‌ریسک','آزمایش جایگزین'] if risk>.45 else ['اقدام اصلی','اعتبارسنجی نتیجه']
            results.append(Prediction(str(action),expected,round(risk,3),round(confidence,3),round(utility,3),total,reversibility,alternatives))
        return sorted(results,key=lambda p:(p.utility,p.confidence,-p.risk),reverse=True)
    def best(self,predictions): return max(predictions,key=lambda p:(p.utility,p.confidence,-p.risk),default=None)
    def counterfactual(self,actions,context=None):
        preds=self.predict(actions,context);return {'ranked':[asdict(p) for p in preds],'best':asdict(preds[0]) if preds else None,'gap':round(preds[0].utility-preds[1].utility,3) if len(preds)>1 else 0.}
    def record(self,action,success,state='',expected=None):
        key=str(action).strip().lower(); ok=float(bool(success));self.stats[key][0]+=ok;self.stats[key][1]+=1
        self.history.append({'action':str(action),'success':bool(success),'state':str(state),'expected':expected});self.history=self.history[-5000:]
        if state and expected:self.transitions[str(state)][str(expected)]+=int(bool(success))
        self._save()
    def calibration(self): return {k:{'success_rate':round(v[0]/v[1],3) if v[1] else 0.,'samples':v[1]} for k,v in self.stats.items()}
    def transition_confidence(self,state,result):
        rows=self.transitions.get(str(state),{});total=sum(rows.values());return round(rows.get(str(result),0)/total,3) if total else 0.

# v0.22: calibrated predictions use state-specific history and empirical outcomes.
def _predict_v2(self,actions,context=None,state=''):
    results=[]
    state_key=str(state).lower().strip()
    for action in actions:
        key=str(action).strip().lower(); risk=self._risk(key); total_score,total=self.stats[key]
        empirical=total_score/total if total else .5
        transition=self.transition_confidence(state_key,key) if state_key else 0
        confidence=max(.08,min(.98,.30*(1-risk)+.30*empirical+.20*.62+.10*transition+.10*min(1,total/10)))
        reversibility=.92 if risk<.2 else .55 if risk<.5 else .18
        utility=confidence*(1-risk)*(0.55+.45*reversibility)
        expected='کم‌ریسک و برگشت‌پذیر' if risk<.2 else 'قابل انجام با آزمون' if risk<.5 else 'پرریسک؛ ابتدا شبیه‌سازی/پشتیبان'
        alts=['بررسی شواهد','اقدام کم‌ریسک','آزمایش جایگزین'] if risk>.45 else ['اقدام اصلی','اعتبارسنجی نتیجه']
        results.append(Prediction(str(action),expected,round(risk,3),round(confidence,3),round(utility,3),total,reversibility,alts))
    return sorted(results,key=lambda p:(p.utility,p.confidence,-p.risk),reverse=True)
PredictionEngine.predict=_predict_v2
