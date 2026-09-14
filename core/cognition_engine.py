from dataclasses import dataclass, field
from core.language_engine import PersianLanguageEngine
from core.semantic import LocalSemanticModel

@dataclass
class CognitiveState:
    intent: str
    goal: str
    entities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    needs_tools: bool = False
    confidence: float = 0.0
    questions: list[str] = field(default_factory=list)
    temporal: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    semantic_features: dict[str,float] = field(default_factory=dict)

class CognitiveEngine:
    """Structured cognition with local semantic features and uncertainty."""
    def __init__(self):
        self.language=PersianLanguageEngine(); self.semantic=LocalSemanticModel()

    def analyze(self,text):
        a=self.language.analyze(text); frame=self.semantic.frame(a.normalized)
        tools={'inspection','debug','build','planning','command'}
        confidence=a.confidence
        if frame.domains: confidence=min(.99,confidence+.02)
        return CognitiveState(a.intent,a.goal,a.entities,a.constraints,a.intent in tools,
            round(confidence,3),a.questions,a.temporal,[],frame.domains,frame.features)

    def propose_hypotheses(self,state,context=None):
        if state.intent=='debug': state.hypotheses=['configuration','implementation','dependency/environment','state/data']
        elif state.intent=='question': state.hypotheses=['direct explanation','context-dependent explanation','alternative explanation','insufficient evidence']
        elif state.intent=='inspection': state.hypotheses=['normal state','degraded state','inconsistent state','unknown without evidence']
        elif state.intent=='build': state.hypotheses=['smallest viable implementation','reuse existing component','refactor then implement']
        else: state.hypotheses=['primary interpretation','contextual interpretation']
        return state.hypotheses

    def enrich(self,text):
        a=self.language.analyze(text); state=self.analyze(text)
        return {'state':state.__dict__,'language':a.__dict__,'negation':self.language.detect_negation(text),
                'sentiment':self.language.sentiment_signal(text),'language_code':a.language,
                'temporal_context':self.language.temporal_context(text),'semantic':self.semantic.frame(text).__dict__}
