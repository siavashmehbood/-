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
        if canonical is None:
            raise RuntimeError("CognitiveKernel is a compatibility adapter; bind CognitiveSystem before cycle()")
        return canonical.kernel_cycle_compat(text)

