"""IRAN v2 cognitive core.

A deterministic, fully-local orchestration layer. It does not generate text itself;
it builds a typed cognitive state from the existing language, memory, graph,
reasoning and user-model subsystems, then verifies the planned response.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any
import re
from pathlib import Path

from core.learning_loop import OutcomeBackedLearning
from core.procedural_skills import ProceduralSkillMemory
from core.state import CognitiveState
from core.programming_learner import ProgrammingLearner

@dataclass
class CognitiveEvidence:
    source: str
    content: str
    confidence: float = 0.5
    kind: str = "memory"

class AdvancedCognitiveCore:
    """Typed cognitive coordinator for IRAN's local subsystems."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.turn = 0
        self.last_state = None
        self.history = []
        learning_engine = getattr(runtime, "learning", None)
        learning_path = getattr(runtime, "learning_path", "data/learning_experiences.json")
        self.outcome_learning = OutcomeBackedLearning(learning_path, learning_engine)
        skill_path = Path(learning_path).with_name("procedural_skills.json")
        self.procedural_skills = ProceduralSkillMemory(skill_path)
        programming_path = getattr(runtime, 'programming_learning_path', 'learning')
        self.programming_learner = ProgrammingLearner(programming_path, self.outcome_learning)

    def practice_programming(self, cycles=1):
        return self.programming_learner.practice(cycles)

    def programming_status(self):
        return self.programming_learner.status()

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
        try:
            from memory.episodic import EpisodicMemory
            episodic = EpisodicMemory(self.runtime.memory)
            rows += [{"source":"episodic", "content":r["content"], "confidence":float(r.get("confidence",.5)), "kind":"episode"}
                     for r in episodic.retrieve(text, 6)]
        except Exception:
            pass
        return rows[:16]

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
        canonical = getattr(self, "_canonical_system", None)
        if canonical is not None:
            return canonical.advanced_core_compat(text)
        self.turn += 1
        parsed = self._parse(text)
        evidence = self._memory(text) + self._graph(text)
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
        self.last_state = state
        self.history.append(state.snapshot())
        self.history = self.history[-100:]
        return state

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

    def record_verified_outcome(self, goal, action, result, expected, verification, strategy="default", domain="general"):
        """Close the cognition -> experience -> learning loop with independent verification."""
        outcome = self.outcome_learning.record_outcome(
            goal, action, result, expected, verification,
            strategy=strategy, domain=domain,
        )
        try:
            self.runtime.events.emit("verified_learning", {
                "goal": str(goal), "verified": bool(outcome["verified"]),
                "learned": bool(outcome["learned"]),
                "verification_source": outcome["verification_source"],
                "score": outcome["score"],
            })
        except Exception:
            pass
        return outcome

    def recommend_from_experience(self, goal, domain="general"):
        """Retrieve prior verified experience without treating retrieval as proof."""
        return self.outcome_learning.recommend(goal, domain)

    def learning_stats(self):
        return self.outcome_learning.stats()

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
