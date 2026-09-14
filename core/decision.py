from dataclasses import dataclass,field

@dataclass
class DecisionOption:
    action:str;utility:float;risk:float;confidence:float;rationale:list[str]=field(default_factory=list);value_of_information:float=0.;reversible:float=.5
@dataclass
class Decision:
    chosen:str;confidence:float;options:list[DecisionOption];reasons:list[str]=field(default_factory=list);deferred:bool=False

class DecisionEngine:
    """Local executive layer using utility, risk, evidence, reversibility and value of information."""
    def choose(self,actions,predictions,evidence=0.):
        options=[]
        for p in predictions:
            voi=max(0.,.22*(1-p.confidence)) if p.risk>.4 else .08*(1-p.confidence)
            bonus=min(.15,float(evidence)); utility=min(1,p.utility+bonus+.05*p.reversibility-voi*.25)
            reasons=['expected utility',f'risk={p.risk:.2f}',f'confidence={p.confidence:.2f}',f'reversibility={p.reversibility:.2f}']
            if p.risk>.5:reasons.append('high-risk action penalized')
            if voi>.08:reasons.append('more information has positive value')
            options.append(DecisionOption(p.action,round(utility,3),p.risk,p.confidence,reasons,round(voi,3),p.reversibility))
        options.sort(key=lambda x:(x.utility,x.confidence,x.reversible,-x.risk),reverse=True)
        if not options:return Decision('',0.,[],['no executable options'],True)
        top=options[0];margin=top.utility-(options[1].utility if len(options)>1 else 0);defer=top.risk>.72 and top.confidence<.7
        conf=max(.1,min(.98,.50*top.confidence+.30*top.utility+.20*min(1,margin*5)))
        reasons=['best expected utility','risk-aware selection']+(['deferred because confidence is insufficient for high-risk action'] if defer else [])
        return Decision('inspect evidence' if defer else top.action,round(conf,3),options,reasons,defer)
