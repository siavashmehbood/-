from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from pathlib import Path

from core.cognitive_pipeline import CognitivePipeline
from core.grounded_synthesizer import GroundedSynthesizer
from core.self_correction import SelfCorrectionEngine
from core.soar_cognitive_engine import SoarCognitiveEngine
from self.cognitive_growth import CognitiveGrowthCycle


@dataclass(frozen=True)
class CognitiveComponents:
    dialogue: Any
    pipeline: CognitivePipeline
    memory: Any
    knowledge: Any
    learning: Any
    reasoning: Any
    planning: Any
    verification: Any
    autonomy: Any
    improvement: Any
    self_directed_learning: Any
    trusted_knowledge: Any
    learning_gate: Any
    cognitive_engine: Any


class CognitiveSystem:
    """Single composition root for the local IRAN cognitive architecture.

    Existing subsystems remain independently testable, but normal execution enters
    through this object so memory, reasoning, planning, verification, learning and
    improvement share one runtime-owned dependency graph.
    """

    VERSION = "2.0-cognitive-os"

    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.dialogue = runtime.dialogue
        self.pipeline = self._get_pipeline()
        self.cognitive_engine = SoarCognitiveEngine(
            runtime.root, getattr(runtime, "memory", None),
            learning_gate=getattr(runtime, "learning_gate", None),
            event_log=getattr(runtime, "events", None))
        self.pipeline.cognitive_engine = self.cognitive_engine
        if getattr(self.dialogue, "grounded_synthesizer", None) is None:
            self.dialogue.grounded_synthesizer = GroundedSynthesizer(
                getattr(runtime, "knowledge", None), getattr(runtime, "memory", None),
                getattr(runtime, "learning", None))
        if getattr(self.pipeline, "self_correction", None) is None:
            self.pipeline.self_correction = SelfCorrectionEngine(
                Path(runtime.root) / "data" / "self_corrections.json")
        self.components = CognitiveComponents(
            dialogue=self.dialogue,
            pipeline=self.pipeline,
            memory=getattr(runtime, "memory", None),
            knowledge=getattr(runtime, "knowledge", None),
            learning=getattr(runtime, "learning", None),
            reasoning=getattr(self.pipeline, "reasoning_planning", None),
            planning=getattr(getattr(self.dialogue, "planner", None), "plan", None),
            verification=getattr(self.pipeline, "semantic_verifier", None),
            autonomy=getattr(runtime, "autonomous_supervisor", None)
            or getattr(runtime, "autonomy", None),
            improvement=getattr(runtime, "improvement", None),
            self_directed_learning=getattr(runtime, "self_directed_learning", None),
            trusted_knowledge=getattr(runtime, "trusted_knowledge", None),
            learning_gate=getattr(runtime, "learning_gate", None),
            cognitive_engine=self.cognitive_engine,
        )
        self.last_answer = ""
        self.last_trace = None
        self.last_output = {}
        self.growth = CognitiveGrowthCycle(Path(runtime.root))

    def _get_pipeline(self) -> CognitivePipeline:
        pipeline = getattr(self.dialogue, "cognitive_pipeline", None)
        if isinstance(pipeline, CognitivePipeline):
            return pipeline
        pipeline = CognitivePipeline(self.dialogue)
        self.dialogue.cognitive_pipeline = pipeline
        self.dialogue._canonical_pipeline = pipeline
        return pipeline

    def dispatch(self, text: str) -> str:
        """Single ingress for every user interaction.

        Commands and natural language now enter the same CognitiveSystem boundary.
        Command execution remains a runtime adapter, while all natural language uses
        the canonical cognitive pipeline. This prevents parallel public entry paths.
        """
        clean_text = str(text or "").strip()
        if not clean_text:
            return "چیزی برای پردازش دریافت نکردم."
        if clean_text.startswith("/"):
            handler = getattr(self.runtime, "_handle_command", None)
            if callable(handler):
                result = handler(clean_text)
                self.last_answer = str(result)
                self.last_trace = getattr(self.dialogue, "last_trace", None)
                self.last_output = self.unified_output()
                return str(result)
        # Learning requests are still decided at the canonical brain boundary; the
        # mission manager owns curriculum/progress only and cannot approve learning.
        try:
            from learning.missions import LearningMissionManager
            learning_intent=LearningMissionManager.parse_intent(clean_text)
        except Exception:
            learning_intent=None
        if learning_intent:
            result=self.runtime._handle_learning_mission_intent(learning_intent,clean_text)
            mission=self.runtime.learning_missions.find(learning_intent.get("topic",""))
            if mission:
                self.dialogue.state.active_goal=f"learning:{mission['mission_id']}:{mission['title']}"
                self.dialogue.state.save(self.dialogue.state_path)
            self.last_answer=str(result)
            self.last_output={"learning_mission":mission.get("mission_id") if mission else None,"answer":self.last_answer}
            return self.last_answer
        routed = getattr(getattr(self.runtime, "orchestrator", None), "router", None)
        if routed is not None:
            tool_name, arguments = routed.choose(clean_text)
            if tool_name and tool_name in {"open_application","screenshot","set_volume","get_battery"}:
                # Phase 2: Phase-1 semantics become a Soar candidate evaluation.
                # CognitiveSystem still owns the allow/deny decision and Jarvis
                # remains a subordinate executor.
                try:
                    slots=self.pipeline.conversation_foundation.current_state().get("slots",{})
                    semantic_turn=self.pipeline.semantic_intelligence.analyze(
                        clean_text,slots=slots,
                        source_turn=int(getattr(self.dialogue.state,"turns",0) or 0)+1)
                    cycle=self.cognitive_engine.cycle(
                        semantic_turn,self.dialogue.state,
                        parsed={"goal":clean_text,"intent":"tool","constraints":[]},
                        tool_candidate=tool_name)
                    self.pipeline.last_semantic_turn=semantic_turn
                    self.pipeline.last_cognitive_cycle=cycle
                    self.dialogue.last_cognitive_trace=cycle.to_dict()
                    if cycle.real_soar and (
                            cycle.safe_abort or cycle.impasse or
                            cycle.selected_operator != tool_name):
                        self.last_answer="عملیات اجرا نشد: موتور شناختی اقدام قابل اتکایی انتخاب نکرد."
                        self.last_output={"computer_action":{"success":False,"reason":"soar_not_authorized"},
                                          "cognitive_cycle":cycle.to_dict(),"answer":self.last_answer}
                        return self.last_answer
                except Exception as exc:
                    self.last_answer="عملیات اجرا نشد: ارزیابی شناختی اقدام در دسترس نیست."
                    self.last_output={"computer_action":{"success":False,"reason":"cognitive_engine_error",
                                                         "error_type":type(exc).__name__},
                                      "answer":self.last_answer}
                    return self.last_answer
                outcome = self.runtime.computer_use.execute(clean_text, tool_name, arguments)
                self.last_answer = ("انجام شد." if outcome.get("success") else
                                    f"عملیات تأیید نشد: {outcome.get('verification',{}).get('reason','unknown')}")
                self.last_output = {"computer_action": outcome,
                                    "cognitive_cycle":cycle.to_dict(),
                                    "answer": self.last_answer}
                return self.last_answer
        return self.turn(clean_text)

    def decide_computer_action(self, goal, observation, previous_actions=None, previous_verification=None, remaining_steps=1):
        """Canonical next-action decision boundary for interactive computer tasks."""
        previous_actions=list(previous_actions or [])
        router=getattr(getattr(self.runtime,"orchestrator",None),"router",None)
        text=str(goal)
        if router is None:return {"status":"safe_stop","reason":"router_unavailable"}
        # Re-observe every step; only select one action. Successful verified actions alter the next decision.
        tool,args=router.choose(text)
        if not tool:return {"status":"safe_stop","reason":"no_grounded_action"}
        if previous_actions and previous_actions[-1].get("tool")==tool:
            last=previous_actions[-1].get("transition_verification",{})
            if last.get("verified"):return {"status":"goal_complete","confidence":1.0}
        expected={"open_application":"window/process appears","screenshot":"artifact exists",
                  "create_folder":"folder exists"}.get(tool,"observable state change")
        verification={"type":"state_change"}
        if tool=="open_application":
            name=str(args.get("name","")); verification={"type":"element_present","label":name}
        return {"status":"act","tool":tool,"arguments":args,"expected":expected,
                "verification":verification,"confidence":.8,"remaining_steps":int(remaining_steps)}

    def turn(self, text: str) -> str:
        """Canonical natural-language turn: perceive -> reason -> act -> verify -> learn."""
        try:
            self.runtime.world.record_observation("user_input", str(text), .85, source="canonical_turn")
        except Exception:
            pass
        answer = self.pipeline.run(text)
        # All legacy short routes must pass the same actual consistency check.
        # This is a narrow check, not proof that a factual claim is true.
        checked = self.pipeline.semantic_verifier.verify(text, answer, evidence=self.pipeline.verification_evidence())
        trace = getattr(self.dialogue, "last_trace", None)
        if trace is not None:
            previous_status = trace.verification_status
            # An UNKNOWN fallback has no new evidence; retain the reason the
            # candidate was rejected before it was persisted.
            if not str(answer).startswith('UNKNOWN:'):
                trace.evidence_status = checked.evidence_status
                trace.evidence_sources = checked.evidence_sources
            if not checked.accepted:
                trace.verification_status = "REPAIR"
            elif previous_status not in {"REPAIR", "CLARIFY", "UNKNOWN"}:
                trace.verification_status = checked.status
            trace.verification_reasons = list(dict.fromkeys(
                list(trace.verification_reasons) + list(checked.reasons) + list(checked.contradictions)))
            trace.confidence = min(trace.confidence, checked.score)
        nonfactual = bool(trace is not None and getattr(trace,"answer_status","") in {"SOCIAL","META","REFERENCE","REEXPLAIN","EXAMPLE","STYLE","FOLLOW_UP","CORRECTION","LEARNING"})
        if not checked.accepted and not nonfactual:
            answer = "UNKNOWN: پاسخ تولیدشده بررسی سازگاری را نگذرانده است."
            self.dialogue.last_answer = answer
        elif not checked.accepted and nonfactual and trace is not None:
            trace.verification_status="PASS"
            trace.verification_reasons=list(dict.fromkeys(list(trace.verification_reasons)+["nonfactual_context_transform"]))
        self.last_answer = answer
        self.last_trace = getattr(self.dialogue, "last_trace", None)
        if str(answer).startswith("UNKNOWN:"):
            self.runtime.self_directed_learning.observe_gap(text, "unknown_answer")
            if self.last_trace is not None:
                self.last_trace.verification_status = "UNKNOWN"
                self.last_trace.confidence = min(.35, self.last_trace.confidence)
            growth = self.growth.evaluate_failure(
                capability="uncertainty_or_knowledge", task=str(text),
                expected="grounded answer or calibrated UNKNOWN", actual=str(answer),
                reason="canonical turn ended UNKNOWN",
                evidence=list(getattr(self.last_trace, "verification_reasons", []) if self.last_trace is not None else []),
                confidence=.85,
            )
            proposed = growth.get("mission")
            if proposed:
                # A detected weakness may create a bounded learning mission, but it
                # never creates an approved learning object. Reviewer -> human ->
                # LearningGate remains the only path that can change cognition.
                self.runtime.learning_missions.create(
                    proposed["goal"], "narrow",
                    source_request=f"weakness:{proposed['weakness_id']}",
                    domain=self.runtime.self_directed_learning.detect_domain(str(text)),
                )
        elif self.last_trace is not None and (self.last_trace.confidence < .5 or self.last_trace.verification_status in {"REPAIR", "CLARIFY"}):
            self.runtime.self_directed_learning.observe_gap(text, "verification_or_confidence_gap")
        # Soar can propose learning only after the canonical verifier has accepted
        # the outcome. The proposal remains pending in IRAN's LearningGate and
        # cannot mutate procedural cognition on its own.
        try:
            cycle=getattr(self.pipeline,"last_cognitive_cycle",None)
            if cycle is not None and getattr(cycle,"real_soar",False) and (
                    getattr(cycle,"impasse",False) or
                    getattr(cycle,"selected_operator","") in {"decompose-goal","retrieve-semantic-memory"}):
                proposal=self.cognitive_engine.propose_learning(
                    cycle, verified=bool(checked.accepted), outcome=str(answer))
                if proposal:
                    self.runtime.events.emit("soar_learning_candidate",{
                        "proposal_id":proposal.get("proposal_id"),
                        "status":proposal.get("status"),"canonical":True})
        except Exception:
            pass
        self._post_turn_learning(text, answer, self.last_trace)
        self.runtime.observe_knowledge_use(text, answer)
        self.last_output = self.unified_output()
        return answer

    def _post_turn_learning(self, text: str, answer: str, trace: Any) -> dict:
        """Evaluate meaningful learning opportunities after every canonical turn."""
        loop = getattr(self.runtime, "effect_learning", None)
        learning = getattr(self.runtime, "learning", None)
        if loop is None or learning is None or trace is None:
            return {}
        try:
            intent = getattr(trace, "intent", "general") or "general"
            feedback_turn = getattr(trace, "answer_status", "") == "FEEDBACK"
            if feedback_turn:
                previous = ""
                for row in reversed(self.runtime.memory.recent(80)):
                    if isinstance(row, (tuple, list)) and len(row) >= 3 and row[0] == "user":
                        candidate = str(row[1]).strip()
                        if candidate and candidate != str(text).strip():
                            previous = candidate
                            break
                goal = previous or str(getattr(trace, "topic", "") or "last_answer")
                effect = loop.evaluate(
                    goal, "explicit-feedback", str(text),
                    "پاسخ قبلی باید با بازخورد مثبت کاربر تأیید شود",
                    {"verified": True, "score": 0.98, "effect_observed": True},
                    strategy="feedback", domain="conversation",
                    episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1)
                self.runtime.events.emit("learning_effect_evaluated", {
                    "goal": goal, "action": "explicit-feedback", "strategy": "feedback",
                    "effect": effect, "canonical": True,
                })
                gate = getattr(self.runtime, "learning_gate", None)
                if gate is not None:
                    proposal = gate.request(
                        "learning.record_experience",
                        {"goal": goal, "action": "explicit-feedback", "result": str(previous or text)[:4000],
                         "score": 0.98, "signal_source": "user_correction", "evidence": str(text)[:1000], "intent": str(intent),
                         "strategy": "feedback", "domain": "conversation"},
                        f"بازخورد مستقیم کاربر: {goal}")
                    if proposal is not None:
                        self.runtime.events.emit("learning_candidate_created", {
                            "proposal_id": proposal.get("proposal_id"), "goal": goal,
                            "source": "user_correction", "canonical": True})
                return {"action": "feedback_validation", "effect": effect, "learning_candidate": proposal if gate is not None else None}
            goal = f"{intent}:{getattr(trace, 'topic', '') or 'conversation'}"
            confidence = float(getattr(trace, "confidence", 0.0) or 0.0)
            priority = loop.learning_priority(
                goal, getattr(trace, "intent", "general") or "general",
                "dialogue", uncertainty=max(0.0, 1.0-confidence),
                novelty=0.6 if not learning.adapt(goal, getattr(trace, "intent", "general") or "general", "dialogue").get("learned_rules") else 0.0)
            action = priority.get("action", "observe_and_wait")
            # Every meaningful turn is a possible learning signal. We collect
            # candidates from success, correction/feedback, repair and failure
            # patterns, then let the existing quality/approval gate decide what
            # becomes durable learning. Candidate volume is intentionally higher
            # than final learning volume.
            verification_status = str(getattr(trace, "verification_status", ""))
            answer_status = str(getattr(trace, "answer_status", ""))
            repaired = bool(getattr(trace, "repair_applied", False) or getattr(trace, "was_repaired", False))
            candidate_score = max(0.0, min(1.0, confidence))
            source = "verified_success" if verification_status == "PASS" else "uncertainty_or_failure"
            if "FEEDBACK" in answer_status or "CORRECT" in answer_status:
                source = "user_correction"
            elif repaired:
                source = "verifier_repair"
            # Knowledge gaps are queued as goals above. Routine outputs and UNKNOWN
            # text are not new knowledge and must not spam the external reviewer.
            # Existing effect-learning remains stricter: only an explicit active
            # experiment or verified historical reuse can mutate effect-learning state.
            if action not in ("active_experiment", "reuse_best_then_verify"):
                observation = loop.observe_behavior(
                    goal, answer, strategy="baseline", domain="dialogue",
                    episode_id=str(getattr(trace, "cycle_id", "") or ""),
                    learning_applied=False,
                )
                priority["learning_state"] = "observe_only"
                priority["effect_learning_recorded"] = False
                priority["behavior_observation"] = observation
                return priority
            # A learning experiment is only credited when the learned strategy
            # produces a measurable behavioral difference against a stored baseline.
            meta = priority.get("meta", {})
            experiment = loop.observe_behavior(
                goal, answer, strategy=str(meta.get("strategy") or getattr(trace, "intent", "general") or "default"),
                domain="dialogue", episode_id=str(getattr(trace, "cycle_id", "") or ""),
                learning_applied=True,
            )
            priority["behavior_experiment"] = experiment
            if experiment.get("mode") != "compared" or not experiment.get("changed"):
                priority["effect_learning_recorded"] = False
                priority["learning_state"] = "experiment_observed"
                return priority
            strategy = str(meta.get("strategy") or getattr(trace, "intent", "general") or "default")
            transfer_source = loop.find_transfer_source(goal, "dialogue", min_similarity=.25)
            if transfer_source is None:
                priority["learning_state"] = "awaiting_transfer_case"
                priority["transfer"] = {"passed": False, "reason": "no_similar_prior_case"}
                priority["effect_learning_recorded"] = False
                return priority
            transfer = loop.evaluate_transfer(
                transfer_source.get("goal",""), goal, answer,
                "رفتار آموخته‌شده باید روی مسئله مشابه نیز با موفقیت اجرا شود",
                {"verified": getattr(trace, "verification_status", "") == "PASS",
                 "score": confidence},
                strategy=strategy, domain="dialogue",
                episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1)
            priority["transfer"] = transfer
            if not transfer.get("passed"):
                priority["learning_state"] = "transfer_failed"
                priority["effect_learning_recorded"] = False
                return priority
            verification = {
                "verified": getattr(trace, "verification_status", "") == "PASS",
                "score": confidence,
                "effect_observed": getattr(trace, "verification_status", "") == "PASS" and confidence >= .75,
            }
            gate = loop.learning_result(experiment.get("comparison", {}), verification, transfer)
            priority["learning_gate"] = gate
            if not gate.get("qualified"):
                priority["learning_state"] = "evidence_chain_incomplete"
                priority["effect_learning_recorded"] = False
                return priority
            expected = "پاسخ در مسیر یادگیری انتخاب‌شده با راستی‌آزمایی و حفظ زمینه اجرا شود"
            result = str(answer)
            effect = loop.evaluate(goal, "canonical_turn", result, expected, verification,
                                   strategy=strategy, domain="dialogue",
                                   episode_id=str(getattr(trace, "cycle_id", "") or ""), attempt=1,
                                   allow_credit=bool(gate.get("xp_eligible")))
            self.runtime.events.emit("learning_effect_evaluated", {
                "goal": goal, "action": action, "strategy": strategy,
                "effect": effect, "canonical": True,
            })
            return {"priority": priority, "effect": effect}
        except Exception as exc:
            try:
                self.runtime.events.emit("learning_effect_error", {"error": str(exc), "canonical": True})
            except Exception:
                pass
            return {}

    def guidance(self, goal: str, intent: str = "general", domain: str = "general") -> dict:
        """Return reusable learned guidance for any cognitive capability, not only dialogue."""
        learning = getattr(self.runtime, "learning", None)
        if learning is None:
            return {}
        try:
            result = learning.adapt(str(goal), str(intent), str(domain)) or {}
            result["failure_signal"] = bool(learning.failure_patterns(6))
            return result
        except Exception:
            return {}

    def record_outcome(self, goal, action, result, expected, verification, strategy="default", domain="general"):
        """Feed a verified outcome back into the shared learning brain."""
        core = getattr(self.runtime, "outcome_learning", None)
        if core is None:
            return {"verified": False, "learned": False, "reason": "outcome_learning_unavailable"}
        return core.record_outcome(goal, action, result, expected, verification,
                                   strategy=strategy, domain=domain)

    def unified_output(self) -> dict:
        """Return the current answer plus the live state of every integrated stage."""
        trace = self.last_trace
        runtime = self.runtime
        return {
            "version": self.VERSION,
            "answer": self.last_answer,
            "trace": trace.__dict__.copy() if trace is not None else {},
            "architecture": self.architecture_contract(),
            "components": self.inspect(),
            "memory": runtime.memory.stats() if getattr(runtime, "memory", None) else {},
            "knowledge": runtime.knowledge.stats() if getattr(runtime, "knowledge", None) else {},
            "learning": self.learning_status(),
            "learning_gate": runtime.learning_status() if hasattr(runtime, "learning_status") else {},
            "autonomy": self.autonomy_status(),
            "improvement": self.improvement_status(),
            "conversation": runtime.conversation_snapshot() if hasattr(runtime, "conversation_snapshot") else {},
            "cognitive_engine": self.cognitive_engine.status(),
        }

    def inspect(self) -> dict:
        """Return a compact live map of the unified dependency graph."""
        runtime = self.runtime
        pipe = self.pipeline
        return {
            "version": self.VERSION,
            "entrypoint": "CognitiveSystem.dispatch",
            "pipeline": "CognitivePipeline.run",
            "memory": type(getattr(runtime, "memory", None)).__name__,
            "knowledge": type(getattr(runtime, "knowledge", None)).__name__,
            "learning": type(getattr(runtime, "learning", None)).__name__,
            "reasoning": type(getattr(pipe, "reasoning_planning", None)).__name__,
            "semantic_verification": type(getattr(pipe, "semantic_verifier", None)).__name__,
            "chain_reasoner": bool(getattr(self.dialogue, "chain_reasoner", None)),
            "grounded_synthesis": bool(getattr(self.dialogue, "grounded_synthesizer", None)),
            "self_correction": bool(getattr(self.pipeline, "self_correction", None) or getattr(self.dialogue, "self_correction", None)),
            "autonomy": bool(
                getattr(runtime, "autonomous_supervisor", None)
                or getattr(runtime, "autonomy", None)
            ),
            "self_improvement": type(getattr(runtime, "improvement", None)).__name__,
            "self_directed_learning": type(getattr(runtime, "self_directed_learning", None)).__name__,
            "trusted_knowledge": type(getattr(runtime, "trusted_knowledge", None)).__name__,
            "learning_gate": type(getattr(runtime, "learning_gate", None)).__name__,
            "soar_cognitive_engine": self.cognitive_engine.status(),
        }

    def learning_status(self) -> dict:
        learning = getattr(self.runtime, "learning", None)
        if learning is None:
            return {"available": False}
        try:
            return {"available": True, **learning.stats()}
        except Exception as exc:
            return {"available": True, "error": str(exc)}

    def improvement_status(self) -> dict:
        improvement = getattr(self.runtime, "improvement", None)
        if improvement is None:
            return {"available": False}
        try:
            return {"available": True, **improvement.status()}
        except Exception as exc:
            return {"available": True, "error": str(exc)}

    def autonomy_status(self) -> dict:
        supervisor = getattr(self.runtime, "autonomous_supervisor", None)
        controller = getattr(self.runtime, "autonomy", None)
        target = supervisor or controller
        if target is None:
            return {"available": False}
        for method in ("snapshot", "status"):
            fn = getattr(target, method, None)
            if callable(fn):
                try:
                    value = fn()
                    return {"available": True, "state": value}
                except Exception:
                    pass
        return {"available": True, "type": type(target).__name__}

    def bind_legacy_adapters(self) -> None:
        """Bind legacy names to this composition root; they remain compatibility adapters."""
        runtime = self.runtime
        for name in ("brain", "cognition_engine", "kernel", "cognitive_core", "orchestrator", "dialogue"):
            component = getattr(runtime, name, None)
            if component is not None:
                try:
                    component._canonical_system = self
                except Exception:
                    pass

    def kernel_cycle_compat(self, text: str):
        """Compatibility view of a kernel cycle without creating a second decision path."""
        from core.kernel import CycleResult
        answer = self.pipeline.run(str(text))
        t = getattr(self.dialogue, "last_trace", None)
        return CycleResult(
            goal=str(text),
            intent=getattr(t, "intent", "general"),
            confidence=float(getattr(t, "confidence", 0.0)),
            reasoning={"canonical": True, "trace": getattr(t, "__dict__", {})},
            predictions=[],
            anomaly={},
            elapsed_ms=float(getattr(t, "elapsed_ms", 0.0)),
            understanding={"answer": answer, "canonical": True},
            causal={},
            strategy={"source": "CognitiveSystem"},
        )

    def advanced_core_compat(self, text: str):
        """Compatibility view of AdvancedCognitiveCore backed by the canonical turn."""
        self.pipeline.run(str(text))
        state = getattr(self.dialogue, "state", None)
        return state if state is not None else {"text": str(text)}

    def close(self) -> None:
        try:
            self.cognitive_engine.close()
        except Exception:
            pass
        self.last_answer = ""
        self.last_trace = None
        self.last_output = {}

    def architecture_contract(self) -> dict:
        """Expose the canonical order used by the integrated turn."""
        return {
            "perception": "dialogue.parse",
            "context": "conversation_state + context_tracker",
            "memory": "MemoryIntelligence + UserModel + episodic/semantic memory",
            "knowledge": "KnowledgeGraph",
            "reasoning": "SoarCognitiveEngine + ChainReasoner + ReasoningPlanningEngine",
            "planning": "AnswerPlanner / planning subsystem",
            "generation": "local deterministic response synthesis",
            "verification": "AnswerVerifier + SemanticVerifier + repair",
            "commit": "ConversationState + memory outcome",
            "learning": "LearningEngine + OutcomeBackedLearning",
            "autonomy": "AutonomousSupervisor / AutonomousController",
            "improvement": "SelfImprovementLoop with sandbox/rollback",
            "entrypoint": "CognitiveSystem.turn",
            "legacy_components": {
                "Brain": "compatibility/input facade",
                "CognitiveEngine": "compatibility facade",
                "AdvancedCognitiveCore": "compatibility facade",
                "CognitiveKernel": "compatibility facade",
                "Orchestrator": "compatibility facade",
            },
            "soar_role": "internal cognitive engine / candidate operator selection",
            "decision_owner": "CognitiveSystem",
            "parallel_decision_paths": False,
        }
