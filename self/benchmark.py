from dataclasses import dataclass,field
from statistics import mean

@dataclass
class BenchmarkResult:
    scores:dict[str,float]=field(default_factory=dict);overall:float=0.;passed:bool=False;details:list[str]=field(default_factory=list)

class CognitiveBenchmark:
    """Capability benchmark for language, ambiguity, memory, reasoning, planning and local response."""
    def run(self,language,provider,brain=None,planner=None,kernel=None):
        scores={};details=[]
        cases=[('build','میخوام یک سیستم بسازی'),('debug','چرا پروژه کار نمی‌کند؟'),('inspection','وضعیت پروژه را بررسی کن'),('question','چرا این کند است؟'),('planning','برای این کار برنامه‌ریزی کن'),('memory','یادت هست درباره پروژه گفتیم؟'),('compare','این بهتره یا قبلی؟')]
        vals=[]
        for expected,text in cases:
            a=language.analyze(text);ok=(a.intent==expected) or (expected=='inspection' and a.intent=='inspection')
            vals.append(float(ok));
            if not ok:details.append(f'language:{expected}!={a.intent}')
        scores['language']=mean(vals)
        amb=language.analyze('این رو قوی‌تر کن');scores['ambiguity']=1.-min(1,amb.ambiguity)
        scores['temporal']=1. if language.temporal_context('فردا بررسی کن')['resolved'] else 0.
        try:
            answer=provider.generate([{'role':'user','content':'سلام'}]);scores['local_response']=1. if len(answer)>40 and 'ایران' in answer else 0.
        except Exception as exc:scores['local_response']=0.;details.append(str(exc))
        if brain:
            try:
                brain.analyze('میخوام یک سیستم بسازی');brain.analyze('این پروژه رو قوی‌تر کن');scores['discourse']=1. if brain.context() else 0.
            except Exception as exc:scores['discourse']=0.;details.append(str(exc))
        if planner:
            try:
                plan=planner.build('یک سیستم بساز',language.analyze('میخوام بسازی'));scores['planning']=1. if len(plan.steps)>=5 and plan.steps[1].depends_on else 0.
            except Exception as exc:scores['planning']=0.;details.append(str(exc))
        if kernel:
            try:
                c=kernel.cycle('چرا پروژه کار نمی‌کند؟');scores['cognition']=1. if c.decision and c.reasoning and c.predictions else 0.
            except Exception as exc:scores['cognition']=0.;details.append(str(exc))
        overall=mean(scores.values()) if scores else 0.
        return BenchmarkResult({k:round(v,3) for k,v in scores.items()},round(overall,3),overall>=.80,details)

# v0.22: behavioral benchmark, not just component-health checks.
def _behavioral(self,provider,brain=None):
    details=[]; scores=[]
    def ask(q):
        try:return provider.generate([{'role':'user','content':q}])
        except Exception as e: details.append('runtime:'+str(e)); return ''
    a=ask('این پروژه چرا کند است و چطور بهترش کنیم؟')
    scores.append(1.0 if ('چرا' not in a or 'چطور' in a or 'مسیر' in a) and len(a)>120 else 0.0)
    a=ask('بین حافظه فعلی و حافظه معنایی کدام بهتر است؟')
    scores.append(1.0 if 'حافظه' in a and ('مقایسه' in a or 'معیار' in a or 'معنایی' in a) else 0.0)
    a=ask('این را بساز ولی بدون اتصال اینترنت و با تست کامل')
    scores.append(1.0 if 'بدون' in a and 'تست' in a and ('هدف' in a or 'برنامه' in a or 'گام' in a) else 0.0)
    return round(sum(scores)/len(scores),3),details

_old_run= CognitiveBenchmark.run
def _run_v2(self,language,provider,brain=None,planner=None,kernel=None):
    result=_old_run(self,language,provider,brain,planner,kernel)
    try:
        behavioral,extra=self._behavioral(provider,brain)
        result.scores['behavioral']=behavioral
        result.details.extend(extra)
        result.overall=round(mean(result.scores.values()),3)
        result.passed=result.overall>=.80
    except Exception as exc: result.details.append('behavioral:'+str(exc))
    return result
CognitiveBenchmark._behavioral=_behavioral
CognitiveBenchmark.run=_run_v2
