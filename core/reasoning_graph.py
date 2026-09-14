from dataclasses import dataclass,field
import re, math

@dataclass
class Evidence:
    text:str; weight:float=.5; source:str='local'; polarity:int=1; reliability:float=.7
@dataclass
class Hypothesis:
    name:str; score:float=0.0; evidence:list[Evidence]=field(default_factory=list); contradictions:list[str]=field(default_factory=list); support:float=0.; opposition:float=0.
@dataclass
class Inference:
    conclusion:str; confidence:float; hypotheses:list[Hypothesis]; assumptions:list[str]=field(default_factory=list); uncertainty:float=1.; chain:list[str]=field(default_factory=list)

class EvidenceReasoner:
    """Offline multi-hypothesis reasoning with weighted evidence, negative evidence and inference chains."""
    def _tokens(self,text):return set(re.findall(r'[\wآ-ی]+',str(text).lower()))
    def _match(self,name,text):
        a=self._tokens(name);b=self._tokens(text);return len(a&b)/max(1,len(a))
    def evaluate(self,goal,hypotheses,evidence=()):
        hs=[]
        for name in hypotheses:
            h=Hypothesis(name)
            for raw in evidence:
                e=raw if isinstance(raw,Evidence) else Evidence(str(raw)); match=self._match(name,e.text)
                if match>.0:
                    h.evidence.append(e); value=match*e.weight*e.reliability
                    if e.polarity>=0:h.support+=value
                    else:h.opposition+=value;h.contradictions.append(e.text)
            h.score=max(0,min(1,h.support-h.opposition));hs.append(h)
        hs.sort(key=lambda x:x.score,reverse=True)
        if not hs:return Inference(goal,0.,[],['no hypotheses'],1.,[])
        top=hs[0]; second=hs[1].score if len(hs)>1 else 0.;margin=max(0,top.score-second);mass=min(1,top.support+top.opposition)
        confidence=max(.08,min(.98,.20+.45*top.score+.22*margin+.13*mass)); uncertainty=round(1-confidence,3)
        assumptions=[] if mass else ['evidence is insufficient or weakly matched']
        chain=[f'goal:{goal}',f'hypothesis:{top.name}',f'support:{top.support:.3f}',f'opposition:{top.opposition:.3f}']
        if len(hs)>1:chain.append(f'runner_up:{hs[1].name}')
        return Inference(top.name,round(confidence,3),hs,assumptions,uncertainty,chain)
    def multi_hop(self,facts,goal,max_hops=3):
        target=self._tokens(goal); current=set(target); chain=[]
        for hop in range(max_hops):
            best=None;best_score=0
            for fact in facts:
                text=' '.join(str(v) for v in fact.values()) if isinstance(fact,dict) else str(fact)
                score=len(current & self._tokens(text))/max(1,len(current))
                if score>best_score:best,best_score=fact,score
            if best is None or best_score<.15:break
            chain.append({'hop':hop+1,'fact':best,'score':round(best_score,3)}); current |= self._tokens(' '.join(str(v) for v in best.values()) if isinstance(best,dict) else str(best))
        return chain
    def contradiction(self,positive,negative):
        a=self._tokens(positive);b=self._tokens(negative);overlap=len(a&b)/max(1,len(a|b));neg=bool(re.search(r'نمی|نیست|نباید|not|false',str(negative).lower()))
        return {'contradiction':overlap>=.2 and neg,'overlap':round(overlap,3)}

# v0.22: stronger evidence scoring with semantic proximity, contradiction and source reliability.
def _evaluate_v2(self,goal,hypotheses,evidence=()):
    hs=[]
    for name in hypotheses:
        h=Hypothesis(name); nt=self._tokens(name)
        for raw in evidence:
            e=raw if isinstance(raw,Evidence) else Evidence(str(raw)); et=self._tokens(e.text)
            if not nt or not et: continue
            overlap=len(nt&et)/max(1,len(nt)); phrase=1.0 if name.lower() in e.text.lower() else 0.0
            match=min(1,.72*overlap+.28*phrase)
            if match<.08: continue
            value=match*float(e.weight)*float(e.reliability)
            if e.polarity>=0:h.support+=value;h.evidence.append(e)
            else:h.opposition+=value;h.contradictions.append(e.text)
        h.score=max(0,min(1,h.support-h.opposition))
        hs.append(h)
    hs.sort(key=lambda x:x.score,reverse=True)
    if not hs:return Inference(goal,0.,[],['no hypotheses'],1.,[])
    top=hs[0]; second=hs[1].score if len(hs)>1 else 0; margin=max(0,top.score-second); mass=min(1,top.support+top.opposition)
    confidence=max(.08,min(.98,.18+.48*top.score+.24*margin+.10*mass)); uncertainty=round(1-confidence,3)
    assumptions=[] if mass else ['evidence is insufficient or weakly matched']
    chain=[f'goal:{goal}',f'hypothesis:{top.name}',f'support:{top.support:.3f}',f'opposition:{top.opposition:.3f}']
    if len(hs)>1:chain.append(f'runner_up:{hs[1].name}')
    return Inference(top.name,round(confidence,3),hs,assumptions,uncertainty,chain)
EvidenceReasoner.evaluate=_evaluate_v2
