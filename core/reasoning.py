from dataclasses import dataclass, field
from core.language_engine import PersianLanguageEngine

@dataclass
class ReasoningResult:
    intent: str
    summary: str
    next_actions: list[str]
    confidence: float
    hypotheses: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    conclusion: str = ''

class Reasoner:
    def __init__(self): self.language=PersianLanguageEngine()
    def analyze(self,text: str, context=None) -> ReasoningResult:
        a=self.language.analyze(text)
        if not a.normalized: return ReasoningResult('empty','No goal supplied.',[],1.0,conclusion='No goal supplied.')
        context=context or []; evidence=[str(x[1]) for x in context[:6]]
        hypotheses=[]
        if a.intent=='debug': hypotheses=['configuration problem','logic/implementation problem','environment/dependency problem']
        elif a.intent=='question': hypotheses=['direct explanation','context-dependent explanation','insufficient evidence']
        elif a.intent=='inspection': hypotheses=['normal state','degraded state','unknown without evidence']
        else: hypotheses=['primary interpretation','alternative interpretation']
        actions=['understand goal','retrieve relevant memory','inspect available evidence']
        if a.intent in {'build','planning'}: actions += ['decompose into steps','compare strategies','execute safest useful step','evaluate result','replan if needed']
        elif a.intent=='debug': actions += ['reproduce problem','isolate cause','test candidate fix','verify regression']
        elif a.intent=='question': actions += ['identify assumptions','compare explanations','check contradictions','state uncertainty']
        else: actions += ['select safe action','observe result','evaluate outcome']
        confidence=a.confidence + (0.05 if evidence else -0.05); confidence=max(.2,min(.99,confidence))
        conclusion='Evidence-backed preliminary conclusion.' if evidence else 'Preliminary conclusion; more evidence is needed.'
        return ReasoningResult(a.intent,a.goal,actions,round(confidence,3),hypotheses,a.constraints,evidence,[],conclusion)

# v0.22: multi-intent reasoning composes actions instead of collapsing to the top intent.
_old_reason=Reasoner.analyze
def _analyze_v2(self,text,context=None):
    result=_old_reason(self,text,context)
    a=self.language.analyze(text)
    if getattr(a,'questions',[]) and any(x in a.normalized for x in ('چرا','چطور','چگونه')):
        result.next_actions=list(dict.fromkeys(result.next_actions+['answer cause','answer method','connect both conclusions']))
        result.summary=a.goal
    if getattr(a,'constraints',[]): result.constraints=list(dict.fromkeys(result.constraints+a.constraints))
    if getattr(a,'alternatives',[]): result.hypotheses=list(dict.fromkeys(result.hypotheses+['alternative interpretation']))
    result.confidence=round(min(.99,result.confidence+.02*len(getattr(a,'entities',[]))),3)
    return result
Reasoner.analyze=_analyze_v2


# v0.31: persistent User Model facts become explicit reasoning evidence.
if not hasattr(Reasoner, '_iran_v31_analyze_base'):
    Reasoner._iran_v31_analyze_base = Reasoner.analyze
_base_v31_reason = Reasoner._iran_v31_analyze_base

def _analyze_v31(self, text, context=None):
    merged = list(context or [])
    model = getattr(self, 'user_model', None)
    if model is not None:
        try:
            merged += [('user_model', f"{f['predicate']}={f['object']} confidence={float(f['confidence']):.2f}")
                       for f in model.facts(limit=8)]
        except Exception:
            pass
    result = _base_v31_reason(self, text, merged)
    result.evidence = list(dict.fromkeys(result.evidence))
    return result

Reasoner.analyze = _analyze_v31
