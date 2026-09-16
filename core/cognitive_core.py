"""IRAN v2 cognitive core.

A deterministic, fully-local orchestration layer. It does not generate text itself;
it builds a typed cognitive state from the existing language, memory, graph,
reasoning and user-model subsystems, then verifies the planned response.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
from core.working_memory import SymbolicWorkingMemory
from core.metacognition import MetacognitiveMonitor
from core.causal_reasoning import CausalGraph
from core.analogical_reasoning import AnalogicalReasoner
from core.production_rules import ProductionSystem
from core.goal_stack import GoalStack
from core.decision_cycle import DecisionCycle
import re

@dataclass
class CognitiveEvidence:
    source: str
    content: str
    confidence: float = 0.5
    kind: str = "memory"

@dataclass
class CognitiveState:
    turn_id: int
    text: str
    intent: str = "general"
    intent_confidence: float = 0.45
    goal: str = ""
    topic: str = ""
    entities: list = field(default_factory=list)
    references: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    plan: list = field(default_factory=list)
    confidence: float = 0.0
    status: str = "understanding"
    executive: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def snapshot(self):
        return asdict(self)

class AdvancedCognitiveCore:
    """Typed cognitive coordinator for IRAN's local subsystems."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.turn = 0
        self.last_state = None
        self.history = []
        self.working_memory = SymbolicWorkingMemory()
        self.metacognition = MetacognitiveMonitor()
        self.causal = CausalGraph()
        self.analogy = AnalogicalReasoner()
        self.production = ProductionSystem()
        self.production.add("respond_to_intent", ("intent:{intent}",), "respond:{intent}", priority=10, confidence=.95)
        self.production.add("verify_with_evidence", ("evidence_available",), "verify_answer", priority=20, confidence=.99)
        self.goals = GoalStack()
        self.decision_cycle = DecisionCycle(self.production, self.goals)

    def _parse(self, text):
        parser = getattr(self.runtime, "dialogue", None)
        frame = parser.snapshot() if parser and hasattr(parser, "snapshot") else {}
        try:
            from core.cognitive_fabric import AdvancedLanguage
            return AdvancedLanguage().parse(text, frame)
        except Exception:
            return {"text": text, "intent": "general", "intent_score": .45,
                    "goal": text, "entities": [], "references": {}}

    def _memory(self, text):
        rows = []
        try:
            rows += [{"source":"memory", "content":r[1], "confidence":.6, "kind":r[0]}
                     for r in self.runtime.memory.working_context(text, 8)]
        except Exception:
            pass
        try:
            rows += [{"source":"semantic", "content":f"{r['subject']} {r['predicate']} {r['value']}",
                      "confidence":float(r.get('confidence',.5)), "kind":"semantic_fact"}
                     for r in self.runtime.memory.semantic_search(text, 6)]
        except Exception:
            pass
        return rows[:12]

    def _graph(self, text):
        try:
            facts = self.runtime.knowledge.query(text, 8)
            return [{"source":"knowledge_graph", "content":str(f),
                     "confidence":float(f.get("confidence",.5)), "kind":"fact"} for f in facts]
        except Exception:
            return []

    def _contradictions(self, text):
        out = []
        try:
            for f in self.runtime.knowledge.query(text, 20):
                if f.get("contradicted_by"):
                    out.append({"fact":f, "alternative":f["contradicted_by"]})
        except Exception:
            pass
        return out

    def _plan(self, parsed):
        intent = parsed.get("intent", "general")
        plans = {
            "question": ["understand", "retrieve", "compare evidence", "answer", "verify"],
            "debug": ["understand", "retrieve context", "isolate cause", "propose fix", "verify"],
            "build": ["understand", "decompose", "inspect dependencies", "execute", "verify"],
            "plan": ["understand", "define goal", "decompose", "rank options", "verify"],
            "compare": ["identify criteria", "retrieve evidence", "normalize options", "compare", "conclude"],
            "memory": ["resolve reference", "retrieve", "verify provenance", "answer"],
        }
        return plans.get(intent, ["understand", "retrieve context", "reason", "answer", "verify"])

    def begin(self, text):
        self.turn += 1
        parsed = self._parse(text)
        self.working_memory.add(text, salience=0.8, tags=[parsed.get("intent", "general")])
        working = [{"source":"working_memory", "content":x[1], "confidence":x[0], "kind":"working"} for x in self.working_memory.recall(text, 6)]
        evidence = working + self._memory(text) + self._graph(text)
        contradictions = self._contradictions(text)
        score = float(parsed.get("intent_score", .45))
        evidence_score = min(1.0, len(evidence) / 5.0)
        contradiction_penalty = .18 if contradictions else 0.0
        confidence = max(.05, min(.99, .62 * score + .28 * evidence_score + .10 - contradiction_penalty))
        unresolved = []
        if confidence < .42:
            unresolved.append("low_confidence")
        if contradictions:
            unresolved.append("contradictory_evidence")
        state = CognitiveState(
            turn_id=self.turn, text=parsed.get("text", text),
            intent=parsed.get("intent", "general"), intent_confidence=score,
            goal=parsed.get("goal", text), topic=parsed.get("goal", text),
            entities=parsed.get("entities", []), references=parsed.get("references", {}),
            evidence=[CognitiveEvidence(**x).__dict__ for x in evidence],
            hypotheses=[x.get("name", "") for x in parsed.get("alternatives", [])],
            contradictions=contradictions, unresolved=unresolved,
            plan=self._plan(parsed), confidence=round(confidence, 3), status="planned")
        self.goals.clear()
        self.decision_cycle.reset()
        self.goals.push(state.goal or text, steps=["respond"])
        executive_facts = [f"intent:{state.intent}"]
        if evidence:
            executive_facts.append("evidence_available")
        executive = self.executive_cycle(executive_facts)
        state.executive = executive.__dict__.copy()
        meta = self.metacognition.assess(confidence, len(evidence), len(contradictions), len(unresolved))
        state.unresolved.extend(meta.issues)
        state.confidence = round(max(0.05, state.confidence - 0.10 * len(meta.issues)), 3)
        self.last_state = state
        self.history.append(state.snapshot())
        self.history = self.history[-100:]
        return state

    def executive_cycle(self, facts, goal=None, steps=None, result=None):
        """Run one symbolic executive cycle over explicit facts and optional goal."""
        if goal and self.goals.current() is None:
            self.goals.push(goal, steps=steps or [])
        return self.decision_cycle.step(facts, result=result)

    def complete_executive(self, answer):
        facts = ["evidence_available"] if str(answer).strip() else []
        result = self.executive_cycle(facts, result=str(answer))
        if self.last_state is not None:
            self.last_state.executive["verification_cycle"] = result.__dict__.copy()
        return result

    def verify(self, state, answer):
        answer = str(answer or "").strip()
        checks = {
            "non_empty": bool(answer),
            "relevant": bool(answer) and bool(state.goal),
            "not_meta_only": not any(x in answer.lower() for x in ("language_analysis", "cognitive_cycle", "plan_created")),
            "uncertainty_honest": not (state.confidence < .42 and len(answer) > 500),
        }
        score = sum(checks.values()) / len(checks)
        state.status = "verified" if score >= .90 else "repair_required"
        return {"passed": score >= .90, "score": round(score, 3), "checks": checks}

    def learn(self, answer, score):
        if not self.last_state:
            return
        self.last_state.status = "learned"
        try:
            self.runtime.events.emit("advanced_cognition", {
                "turn": self.last_state.turn_id,
                "intent": self.last_state.intent,
                "confidence": self.last_state.confidence,
                "evidence_count": len(self.last_state.evidence),
                "contradictions": len(self.last_state.contradictions),
                "verification": float(score),
            })
        except Exception:
            pass

