from dataclasses import dataclass,asdict
from time import perf_counter
from .cognition_engine import CognitiveEngine
from .reasoning import Reasoner
from .reasoning_graph import EvidenceReasoner,Evidence
from .decision import DecisionEngine
from .reflection import ReflectionEngine
from .cognitive_fabric import AdvancedLanguage,CausalGraph,StrategyMemory

@dataclass
class CycleResult:
    goal:str;intent:str;confidence:float;reasoning:dict;predictions:list;anomaly:dict;elapsed_ms:float
    decision:dict=None;reflection:dict=None;understanding:dict=None;causal:dict=None;strategy:dict=None

class CognitiveKernel:
    """Full local cognition loop with semantic parsing, evidence, prediction, decision and metacognition."""
    def __init__(self,memory,world,knowledge,prediction,anomaly,learning=None):
        self.memory=memory;self.world=world;self.knowledge=knowledge;self.prediction=prediction;self.anomaly=anomaly;self.learning=learning
        self.cognition=CognitiveEngine();self.reasoner=Reasoner();self.evidence=EvidenceReasoner();self.decider=DecisionEngine();self.reflector=ReflectionEngine();self.outcome_learning=None
        self.language=AdvancedLanguage();self.causal=CausalGraph();self.strategies=StrategyMemory()
    def cycle(self,text):
        canonical = getattr(self, "_canonical_system", None)
        if canonical is not None:
            return canonical.kernel_cycle_compat(text)
        started=perf_counter();understanding=self.language.parse(text);state=self.cognition.analyze(text)
        context=self.memory.working_context(state.goal,10);self.cognition.propose_hypotheses(state,context)
        evidence=[Evidence(str(row[1]),.45,'memory',1,.78) for row in context if len(row)>=2]
        inference=self.evidence.evaluate(state.goal,state.hypotheses,evidence)
        reasoning=self.reasoner.analyze(state.goal,context)
        anomaly=self.anomaly.observe(state.intent)
        domain=state.domains[0] if state.domains else 'general'
        strategy=self.learning.adapt(state.goal,state.intent,domain) if self.learning else {'recommended_strategy':'evidence-first'}
        if self.learning: strategy['derived_rule']=self.learning.derive_rule(state.goal,state.intent,domain)
        known=self.knowledge.query(state.goal,8)
        if known: inference.chain.append(f'knowledge_matches:{len(known)}')
        predictions=self.prediction.predict(reasoning.next_actions,context,state.goal)
        learned_choice = {}
        if self.outcome_learning:
            try:
                learned_choice=self.outcome_learning.recommend_action(state.goal, reasoning.next_actions, domain)
            except Exception:
                learned_choice={}
        decision=self.decider.choose(reasoning.next_actions,predictions,len(evidence)/10,learned_choice)
        if learned_choice:
            strategy['verified_experience'] = learned_choice
        causal=self.causal.counterfactual(state.intent,decision.chosen,'inspect evidence') if decision.chosen else {}
        self.world.record_observation('intent',state.intent,state.confidence);self.world.record_event('cognitive_cycle',{'goal':state.goal,'intent':state.intent,'confidence':state.confidence,'inference':inference.conclusion,'uncertainty':inference.uncertainty})
        if decision.chosen:self.world.transition(state.intent,decision.chosen,'pending-observation',decision.confidence)
        self.memory.add('cognitive_state',{'goal':state.goal,'intent':state.intent,'hypotheses':state.hypotheses,'decision':decision.chosen,'uncertainty':inference.uncertainty},.55)
        reflection=self.reflector.reflect(state.goal,'cycle completed',decision.confidence,predictions)
        elapsed=round((perf_counter()-started)*1000,3)
        return CycleResult(state.goal,state.intent,state.confidence,{'reasoning':asdict(reasoning),'evidence_inference':asdict(inference)},[asdict(p) for p in predictions],asdict(anomaly),elapsed,asdict(decision),asdict(reflection),understanding,causal,strategy)

# v0.22: expose the internal evidence graph to the response layer instead of hiding cognition behind templates.
_old_cycle=CognitiveKernel.cycle
def _cycle_v2(self,text):
    result=_old_cycle(self,text)
    try:
        knowledge=self.knowledge.query(result.goal,8)
        result.understanding=result.understanding if isinstance(result.understanding,dict) else {}
        result.understanding.update({'knowledge':knowledge,'memory_evidence':result.reasoning.get('evidence_inference',{}).get('hypotheses',[]),
            'world':self.world.infer(result.intent,8),'temporal':self.world.temporal_summary(6)})
        result.reasoning['evidence_texts']=[x.get('text','') for x in result.reasoning.get('evidence_inference',{}).get('hypotheses',[])[:4] if isinstance(x,dict)]
        result.reflection['next_steps']=result.reflection.get('next_steps',[])+['update knowledge/world state','calibrate response quality']
    except Exception: pass
    return result
CognitiveKernel.cycle=_cycle_v2
