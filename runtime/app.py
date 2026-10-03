"""Canonical local runtime for the IRAN cognitive architecture."""
from pathlib import Path
from persistence import json_transaction, file_lock, load_json_with_backup, load_critical_json, acquire_runtime_ownership, StateCorruptionError
import json
import hashlib
import threading
from learning.approval_transaction import serialized, recover, approval_checkpoint
import re

from core.agent import Agent
from core.brain import Brain
from core.cognition_engine import CognitiveEngine
from core.world_model import WorldModel
from core.prediction import PredictionEngine
from core.anomaly import AnomalyDetector
from core.kernel import CognitiveKernel
from core.reflection import ReflectionEngine
from core.answer_generator import AnswerGenerator
from core.response_engine import LocalResponseEngine
from core.rule_engine import SymbolicRuleEngine
from core.autonomy import AutonomousController
from core.autonomous_supervisor import AutonomousSupervisor
from core.action_runtime import ActionExecutor
from core.observation import ObservationEngine
from core.verification import VerificationEngine
from core.failure import FailureIntelligence
from core.replanning import Replanner
from core.adaptive_execution import AdaptiveExecutionPolicy
from core.dialogue import LocalDialogueEngine
from core.cognitive_core import AdvancedCognitiveCore
from core.user_model import UserModel
from core.world.transition import TransitionRecorder
from language_intelligence import PersianIntelligence
from memory.store import Memory
from knowledge.knowledge_graph import KnowledgeGraph
from learning.learning_engine import LearningEngine
from learning.effect_loop import EffectLearningLoop
from learning.generalizer import GeneralizationEngine
from learning.replay import ExperienceReplay
from learning.versioning import BrainVersionStore
from memory.error import ErrorMemory
from memory.consolidation import MemoryConsolidator
from core.meta_reasoner import MetaReasoner
from evaluation.regression import RegressionGate
from learning.self_directed import SelfDirectedLearning
from learning.missions import LearningMissionManager
from learning.trusted_knowledge import TrustedKnowledgeBootstrap
from learning.procedural_memory import ProceduralMemory
from learning.skill_system import SkillSystem
from learning.internet_learning import InternetLearningEngine
from learning.capability_learning import CapabilityLearningEngine
from learning.input_fabric import InputFabric
from providers.factory import create_provider
from runtime.events import EventLog
from runtime.goals import GoalStore
from runtime.scheduler import Scheduler
from runtime.runner import BackgroundRunner
from runtime.task_runtime import TaskRuntime, TaskStatus
from runtime.conversation_router import ConversationRouter
from security.policy import SecurityPolicy
from security.learning_gate import LearningGate
from security.review_decision_journal import ReviewDecisionJournal
from security.internet_access import InternetAccessManager
from tools.builtin import build_registry
from self.evaluator import Evaluator
from self.benchmark import CognitiveBenchmark
from self.improvement_loop import SelfImprovementLoop
from integrations.chatgpt_review_worker import ChatGPTReviewWorker
from providers.reviewer import ProviderManager


class IranRuntime:
    """Single runtime composition root; ordinary turns enter CognitiveSystem."""

    def __init__(self, root):
        self.root = Path(root)
        self._ownership = acquire_runtime_ownership(self.root / 'data/runtime_owner.lock')
        try:
            self._initialize()
        except BaseException:
            self.close()
            raise

    def _initialize(self):
        self._mutation_lock = threading.RLock()
        self._recovery_required = False
        recover(self.root)
        self.config = json.loads((self.root / "config.json").read_text(encoding="utf-8-sig"))
        self.provider = create_provider(self.config)
        self.learning_gate = LearningGate(self.root / "data/learning_proposals.json")
        self.chatgpt_review_worker = ChatGPTReviewWorker(self.root)
        self.trusted_knowledge = TrustedKnowledgeBootstrap()
        self.self_directed_learning = SelfDirectedLearning(self.root / "data/learning_goals.json")
        self.learning_missions = LearningMissionManager(self.root / "data/learning_missions.json")
        # Curriculum goals are generated only by the autonomous learning intake.
        self.trusted_knowledge_path = self.root / "data/trusted_knowledge.json"
        load_critical_json(self.trusted_knowledge_path, [])
        self.memory = Memory(self.root / self.config["memory"]["db"], gate=self.learning_gate)
        self.events = EventLog(self.root / self.config["runtime"]["event_log"])
        self.goals = GoalStore(self.root / self.config["runtime"].get("goals", "data/goals.json"))
        self.internet_access = InternetAccessManager(self.root / "data/internet_access.json")
        reviewer_config = load_json_with_backup(self.root / "reviewers.local.json", self.config.get("reviewers", {}))
        self.reviewer_manager = ProviderManager(self.root, {"reviewers": reviewer_config, "external_access": self.config.get("external_access", {})}, self.internet_access)
        self.chatgpt_review_worker.manager = self.reviewer_manager
        if hasattr(self.provider, "reviewer_manager"):
            self.provider.reviewer_manager = self.reviewer_manager
        self.policy = SecurityPolicy(self.config, internet_access=self.internet_access)
        self.registry = build_registry(self.root, self.memory, self.internet_access)
        self.brain = Brain(self.provider)
        self.agent = Agent(self.brain, self.memory, self.config["memory"]["max_history"])
        self.evaluator = Evaluator(self.root)
        self.benchmark = CognitiveBenchmark()
        self.improvement = SelfImprovementLoop(self.root)
        self.cognition_engine = CognitiveEngine()
        self.world = WorldModel(self.root / "data/world.json")
        self.knowledge = KnowledgeGraph(self.root / "data/knowledge.json", gate=self.learning_gate)
        self.learning = LearningEngine(self.root / "data/experiences.json", gate=self.learning_gate)
        self.generalizer = GeneralizationEngine(self.learning)
        self.replay = ExperienceReplay(self.learning)
        self.error_memory = ErrorMemory(self.root / "data/error_memory.json")
        self.version_store = BrainVersionStore(self.root / "data/brain_versions.json")
        self.memory_consolidator = MemoryConsolidator(self.memory)
        self.meta_reasoner = MetaReasoner()
        self.regression_gate = RegressionGate(self.root / "data/regression_gate.json")
        self.prediction = PredictionEngine(self.root / "data/predictions.json")
        self.anomaly = AnomalyDetector()
        self.kernel = CognitiveKernel(self.memory, self.world, self.knowledge,
                                      self.prediction, self.anomaly, self.learning)
        self.rules = SymbolicRuleEngine()
        self.rules.add("پروژه ایران", "معماری شناختی", .95, "project_definition")
        self.rules.add("معماری شناختی", "نیازمند حافظه و استدلال", .9, "architecture_principle")
        self.answer_generator = AnswerGenerator(
            getattr(self.provider, "response_engine", None) or LocalResponseEngine(), self.knowledge)
        self.reflector = ReflectionEngine()
        self.scheduler = Scheduler(self.root / "data/schedule.json")
        self.runner = BackgroundRunner(self.scheduler, self.events)
        self.tasks = TaskRuntime(self.root / "data/tasks.json")
        self.actions = ActionExecutor(self.registry, self.policy, self.events)
        from core.computer_use import ComputerUse
        self.computer_use = ComputerUse(self)
        self.observer = ObservationEngine(self.events)
        self.verifier = VerificationEngine(self.events)
        self.failure = FailureIntelligence()
        self.replanner = Replanner(self.events)
        self.adaptive_execution = AdaptiveExecutionPolicy(max_replans=1)
        self.transition_recorder = TransitionRecorder(self.world)
        from core.learning_loop import OutcomeBackedLearning
        self.effect_learning = EffectLearningLoop(self.root / "data/effect_learning.json", self.learning)
        self.outcome_learning = OutcomeBackedLearning(
            self.root / "data/verified_outcomes.json", self.learning, self.learning_gate,
            effect_loop=self.effect_learning)
        self.procedural_memory = ProceduralMemory(self.root / "data/procedures.json", gate=self.learning_gate)
        self.skills = SkillSystem(self.root / "data/skills.json", self.procedural_memory, gate=self.learning_gate)
        self.user_model = UserModel(self.memory, self.knowledge, "IRAN", gate=self.learning_gate)
        self.internet_learning = InternetLearningEngine(self)
        self.capability_learning = CapabilityLearningEngine(self)
        # Unified ingress: every learning-relevant input is normalized, classified,
        # provenance-tagged and deduplicated before the cognitive system sees it.
        self.input_fabric = InputFabric(self.root, runtime=self)
        self.language_intelligence = PersianIntelligence(self.brain.language)
        self.conversation_router = ConversationRouter(self)
        from core.orchestrator import Orchestrator
        self.orchestrator = Orchestrator(
            self.agent, self.memory, self.events, self.registry, self.policy,
            self.goals, self.evaluator)
        self.orchestrator._user_model = self.user_model
        self.orchestrator.planner.learning = self.learning
        self.orchestrator.planner.generalizer = self.generalizer
        self.agent._user_model = self.user_model
        self.kernel.outcome_learning = self.outcome_learning
        self.kernel.skill_system = self.skills
        self.kernel.procedural_memory = self.procedural_memory
        self.kernel._iran_runtime_owner = self
        self.autonomy = AutonomousController(self)
        self.autonomy.restore()
        self.autonomous_supervisor = AutonomousSupervisor(self)
        self.dialogue = LocalDialogueEngine(self)
        self.cognitive_core = AdvancedCognitiveCore(self)
        from core.cognitive_system import CognitiveSystem as _CognitiveSystem
        self.cognitive_system = _CognitiveSystem(self)
        self.cognitive_system.bind_legacy_adapters()
        self.orchestrator.verified_executor = self.execute_verified_goal
        # Reconcile interrupted reviewer/Gate writes, then rebuild any missing
        # observational audit events. This path never approves pending learning.
        if self._chatgpt_review_path().exists():
            self.sync_chatgpt_learning_reviews()
        self._seed_local_knowledge()
        self.events.emit("runtime_ready", {"provider": self.provider.name,
            "version": self.config["version"], "cognitive": True,
            "offline": True, "network_model": False})

    def _seed_local_knowledge(self):
        facts = (("ایران", "پایتخت", "تهران", .99),
                 ("فرانسه", "پایتخت", "پاریس", .99),
                 ("ایران", "نام", "ایران", .99))
        with self.learning_gate.bypass():
            for subject, predicate, object_, confidence in facts:
                if not self.knowledge.best_fact(subject, predicate):
                    self.knowledge.add_fact(subject, predicate, object_, confidence,
                                            "verified_local_seed")

    @serialized
    def handle(self, text):
        # One public ingress: capture the learning signal first, then let CognitiveSystem
        # own the decision between conversation, learning missions and tools.
        self.input_fabric.ingest(text, source="user", input_type="conversation",
                                 provenance={"channel": "runtime.handle"}, create_goal=True)
        return self.cognitive_system.dispatch(text)

    def _handle_learning_mission_intent(self, intent, source_request=""):
        action, topic = intent.get("action"), intent.get("topic", "")
        if str(topic).strip().lower() in {"این موضوع", "همین موضوع", "موضوع فعلی", "this topic"}:
            dialogue_state = getattr(getattr(self, "dialogue", None), "state", None)
            topic = str(getattr(dialogue_state, "current_topic", "") or "").strip()
            if not topic:
                previous = self.learning_missions.find("")
                topic = previous.get("title", "") if previous else ""
            if not topic:
                return "برای افزودن این موضوع، ابتدا موضوع را در گفت‌وگو مشخص کنید."
        mission = self.learning_missions.find(topic)
        if action == "create":
            mission = self.learning_missions.create(
                topic, intent.get("scope", "full"), source_request,
                self.self_directed_learning.detect_domain(topic))
            current = next((u for u in mission.get("units", []) if u.get("unit_id") == mission.get("current_unit")), None)
            if current and current.get("status") in {"waiting_for_reviewer", "waiting_for_human"}:
                return self.learning_missions.status_text(mission) + "\nاین درس در انتظار بررسی است و candidate تکراری ساخته نمی‌شود."
            lesson = self.learning_missions.lesson(mission["mission_id"])
            if lesson and lesson.get("ok") is not False:
                return (f"مأموریت «{mission['title']}» ایجاد/بازیابی شد ({intent.get('scope', 'full')}). "
                        f"برنامهٔ درسی {len(mission['units'])} بخش دارد.\n\n"
                        f"درس آغازین — {lesson['objective']}\n{lesson['explanation']}\n"
                        f"تمرین: {lesson['practice'][0]}\nآزمون: {lesson['assessment'][0]}\n"
                        "پس از انجام تمرین، نتیجه و شواهد واقعی را ارسال کنید تا ارزیابی ثبت شود؛ تا آن زمان هیچ دانشی به مخزن پایدار اضافه نمی‌شود.")
            return f"مأموریت «{topic}» ایجاد شد؛ پیش‌نیازهای درس فعلی هنوز باید گذرانده شوند."
        if action == "status":
            return self.learning_missions.status_text(mission)
        if not mission:
            return f"مأموریت «{topic or 'موضوع درخواستی'}» پیدا نشد؛ برای ساخت آن درخواست روشنِ «… را یاد بده» بفرستید."
        if action == "pause":
            self.learning_missions.pause(mission["mission_id"])
            return f"مأموریت «{mission['title']}» متوقف شد؛ نقطهٔ ادامه ذخیره شد."
        if action == "continue":
            mission = self.learning_missions.resume(mission["mission_id"])
            current = next((u for u in mission.get("units", []) if u.get("unit_id") == mission.get("current_unit")), None)
            if current and current.get("status") in {"waiting_for_reviewer", "waiting_for_human"}:
                return self.learning_missions.status_text(mission) + "\nاین درس در صف بازبینی/تأیید است؛ درس جدید یا candidate تکراری ایجاد نشد."
            lesson = self.learning_missions.lesson(mission["mission_id"])
            if lesson and lesson.get("ok") is False:
                return f"مأموریت «{mission['title']}» از checkpoint بازیابی شد؛ پیش‌نیاز {lesson['missing']} هنوز کامل نشده است."
            if lesson:
                return f"مأموریت «{mission['title']}» از checkpoint ادامه یافت.\n{lesson['explanation']}\nتمرین: {lesson['practice'][0]}"
            return self.learning_missions.status_text(mission)
        return "فرمان مأموریت یادگیری شناخته نشد."

    def learning_missions_status(self):
        """Durable mission dashboard data; safe for GUI refreshes."""
        return self.learning_missions.list()

    def prepare_mission_lesson(self, mission_id, unit_id=None):
        lesson = self.learning_missions.lesson(mission_id, unit_id)
        if lesson and lesson.get("ok") is not False:
            unit_id = lesson["unit_id"]
            def apply(mission, state):
                unit = next((u for u in mission["units"] if u["unit_id"] == unit_id), None)
                if unit and unit.get("status") in {"planned", "remediation"}:
                    unit["status"] = "practicing"
                    mission["status"] = "practicing"
                    mission["next_action"] = "complete_practice_and_assessment"
                    mission["resume_checkpoint"] = unit_id
            self.learning_missions._mutate(mission_id, apply)
        return lesson

    @staticmethod
    def _mission_candidate_validation(unit, lesson, evidence):
        text = " ".join(str(x) for x in (unit.get("title"), unit.get("expected_knowledge"), lesson, evidence)).lower()
        meta_markers = ("edition was published", "published in 20", "نوبت چاپ", "ویرایش کتاب در", "تاریخ انتشار")
        if any(marker in text for marker in meta_markers):
            return False, "metadata_only"
        target_tokens = set(re.findall(r"[\wآ-ی]+", (unit.get("title", "") + " " + unit.get("expected_knowledge", "")).lower()))
        evidence_tokens = set(re.findall(r"[\wآ-ی]+", str(evidence).lower()))
        target_tokens -= {"a", "an", "the", "in", "for", "and", "of", "to", "can", "learner", "explain", "accurately", "check", "study", "focused", "on", "را", "در", "از", "و", "به"}
        overlap = len(target_tokens & evidence_tokens) / max(1, len(target_tokens))
        if len(evidence_tokens) < 5 or overlap < .15:
            return False, "topic_drift"
        if not str(lesson).strip():
            return False, "insufficient_learning_value"
        return True, "accepted"

    @serialized
    def submit_mission_assessment(self, mission_id, unit_id, score, evidence,
                                  practice_result="", transfer_success=False,
                                  weak_concepts=None, lesson_text=None, sources=None):
        """Persist assessment and, on pass, stage a mission candidate pre-Gate."""
        mission = self.learning_missions.get(mission_id)
        if not mission:
            return {"ok": False, "reason": "mission_not_found"}
        unit = next((u for u in mission["units"] if u["unit_id"] == unit_id), None)
        if not unit:
            return {"ok": False, "reason": "unit_not_found"}
        lesson = lesson_text or (self.learning_missions.lesson(mission_id, unit_id) or {}).get("explanation", "")
        valid, reason = self._mission_candidate_validation(unit, lesson, str(evidence))
        if not valid:
            return {"ok": False, "reason": reason, "reason_code": reason}
        outcome = self.learning_missions.record_assessment(
            mission_id, unit_id, score, evidence, practice_result, transfer_success, weak_concepts)
        if not outcome or not outcome.get("ok") or outcome.get("remediation"):
            return outcome or {"ok": False, "reason": "assessment_not_recorded"}
        assessment = outcome["assessment"]
        if outcome.get("duplicate"):
            rows = load_critical_json(self._chatgpt_review_path(), [])
            existing = next((r for r in rows if (r.get("payload") or {}).get("mission_id") == mission_id
                             and (r.get("payload") or {}).get("unit_id") == unit_id
                             and (r.get("payload") or {}).get("assessment_result", {}).get("assessment_id") == assessment.get("assessment_id")), None)
            if existing:
                return {**outcome, "candidate": existing, "gate_unchanged": True}
        prior_evidence = " ".join(str(e.get("evidence", "")) for e in unit.get("evidence_history", []))
        relevance_score = self.self_directed_learning.relevance(unit["title"], evidence)
        novelty_score = self.self_directed_learning.novelty(unit["title"], evidence, prior_evidence)
        domain = mission.get("domain", "general")
        candidate_type = ("language" if domain in {"english", "persian_literature", "arabic"} else
                          "skill" if domain in {"programming", "computer_science"} else "lesson")
        payload = {
            "goal": mission["title"], "lesson": lesson,
            "confidence": float(assessment["score"]), "source": "learning_mission_assessment",
            "domain": mission.get("domain", "general"), "mission_id": mission_id,
            "mission_title": mission["title"], "unit_id": unit_id,
            "unit_title": unit["title"], "learning_objective": unit["objectives"][0],
            "candidate_type": candidate_type, "claim": lesson, "evidence": str(evidence),
            "sources": list(sources or []), "practice_result": str(practice_result),
            "assessment_result": assessment, "novelty_score": novelty_score,
            "relevance_score": relevance_score, "learning_value_score": round((relevance_score + assessment["score"]) / 2, 4),
            "expected_effect": unit["expected_skill"],
            "prerequisite_context": unit.get("prerequisites", []),
            "why_this_should_be_learned": unit["description"],
        }
        candidate = self.queue_learning_candidate("memory.add_lesson", payload,
                                                  f"{mission['title']} — {unit['title']}")
        self.learning_missions.mark_candidate(mission_id, unit_id, candidate["proposal_id"])
        return {**outcome, "candidate": candidate, "gate_unchanged": True}

    @serialized
    def record_mission_effect(self, mission_id, unit_id, verified, score, observation,
                              transfer_success=False):
        """Record post-approval transfer evidence and feed its result to Effect Learning."""
        mission = self.learning_missions.get(mission_id)
        unit = next((u for u in (mission or {}).get("units", []) if u.get("unit_id") == unit_id), None)
        if not mission or not unit:
            return {"ok": False, "reason": "mission_or_unit_not_found"}
        if unit.get("status") != "mastered" or not unit.get("approved_learning_ids"):
            return {"ok": False, "reason": "human_approved_learning_required"}
        verified = bool(verified and transfer_success)
        result = self.effect_learning.evaluate(
            mission["title"], "mission_unit_transfer_assessment", str(observation),
            unit.get("expected_skill", ""),
            {"verified": verified, "score": float(score), "effect_observed": verified,
             "source": "mission_transfer_assessment"},
            strategy="learning_mission", domain=mission.get("domain", "general"),
            episode_id=f"{mission_id}:{unit_id}", attempt=len(unit.get("effect_history", [])) + 1,
            allow_credit=False)
        updated = self.learning_missions.record_effect(mission_id, unit_id, verified, score, observation)
        self.events.emit("mission_effect_evaluated", {
            "mission_id": mission_id, "unit_id": unit_id,
            "verified": verified, "score": float(score), "effect": result.get("effect")})
        return {"ok": True, "mission": updated, "effect_learning": result}

    @serialized
    def ingest_input(self, content, source="system", input_type="other", **kwargs):
        """Public multi-source learning ingress for documents, web, code, feedback and experiments."""
        return self.input_fabric.ingest(content, source=source, input_type=input_type, **kwargs)

    @serialized
    def ingest_inputs(self, items, **kwargs):
        return self.input_fabric.ingest_batch(items, **kwargs)

    def input_fabric_status(self):
        return self.input_fabric.stats()

    def _apply_approved_outcome(self, p):
        outcome=self.outcome_learning
        identity = lambda row: tuple(str(row.get(k, "")) for k in ("goal", "action", "result", "strategy", "domain"))
        if not any(identity(row) == identity(p) for row in outcome.records):
            outcome.records.append(dict(p)); outcome._save()
        result = {"recorded": True, "verified": bool(p.get("verified")), "learned": False}
        if bool(p.get("verified")) and self.learning is not None:
            learned = self.learning.record(
                p.get("goal",""), p.get("action",""), p.get("result",""), p.get("score",0),
                intent="verified_outcome", strategy=p.get("strategy","default"), domain=p.get("domain","general"),
            )
            result.update(learned or {})
            result["learned"] = True
            result["effect_learning"] = self.effect_learning.evaluate(
                p.get("goal",""), p.get("action",""), p.get("result",""),
                p.get("expected", ""), {"verified": bool(p.get("verified")), "score": p.get("score",0), "source": p.get("verification_source","approval")},
                p.get("strategy","default"), p.get("domain","general"), p.get("episode_id",""), p.get("attempt",0))
            # Two independently approved successes of the same action form a
            # reusable local skill. This promotion happens inside approval.
            if float(p.get("score", 0)) >= .75:
                rows = [
                    r for r in outcome.records
                    if r.get("verified") and float(r.get("score", 0)) >= .75
                    and r.get("action") == p.get("action") and r.get("domain") == p.get("domain")
                ]
                if len(rows) >= 2:
                    skill = self.skills.upsert(
                        name=f"learned:{p.get('action')}",
                        description=f"Verified local skill learned from repeated outcomes: {p.get('action')}",
                        domain=p.get("domain","general"),
                        goal_patterns=[str(p.get("goal",""))],
                        procedure={"steps": [{"action": str(p.get("action","")), "expected_effect": str(p.get("expected",""))}],
                                   "expected_outcome": str(p.get("expected",""))},
                        preconditions=[], confidence=min(.99, .75 + .05 * len(rows)),
                    )
                    self.events.emit("skill_learned", {
                        "skill_id": skill.get("skill_id") if isinstance(skill, dict) else None,
                        "action": p.get("action"), "samples": len(rows),
                    })
                    result["skill"] = skill
        return result

    def bootstrap_trusted_knowledge(self, topic, sources):
        """Learn only evidence that is relevant to the active learning goal."""
        combined = " ".join(str(s.get("text", "")) for s in (sources or []))
        confidence = max((float(s.get("source_confidence", 0)) for s in (sources or [])), default=0.0)
        goal = self.self_directed_learning.goal_for(topic, combined, "", confidence)
        decision = goal["decision"]
        if not decision["learn"]:
            return {"status": "needs_review", "reason": "self_directed_relevance_gate",
                    "topic": topic, "learning_goal": goal, "sources": len(sources or [])}
        proposal = self.trusted_knowledge.build(topic, sources)
        proposal["learning_goal"] = goal
        if proposal.get("status") != "ready_for_review":
            return proposal
        candidate = self.queue_learning_candidate(
            "trusted_knowledge.bootstrap", proposal,
            f"Trusted knowledge bootstrap: {topic}",
        )
        return candidate or proposal

    def _apply_trusted_knowledge(self, proposal):
        path = self.trusted_knowledge_path
        rows = load_critical_json(path, [])
        payload = proposal.get("payload") or proposal
        bundle = {
            "proposal_id": payload.get("proposal_id"),
            "gate_proposal_id": proposal.get("proposal_id") if proposal.get("payload") else None,
            "review": self.chatgpt_learning_review_status(proposal.get("proposal_id")) if proposal.get("payload") else {},
            "topic": payload.get("topic"),
            "confidence": payload.get("confidence", 0),
            "agreements": payload.get("agreements", []),
            "sources": payload.get("sources", []),
            "approved_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        if not bundle["proposal_id"]:
            return {"stored": False, "reason": "missing_proposal_id"}
        duplicate = any(r.get("proposal_id") == bundle["proposal_id"] for r in rows)
        if not duplicate:
            rows.append(bundle)
            from persistence import atomic_write_json
            atomic_write_json(path, rows)
        for agreement in bundle["agreements"]:
            claim = str(agreement.get("claim", "")).strip()
            if not claim: continue
            source_id = "trusted_knowledge:" + str(bundle["proposal_id"])
            self.knowledge.add_fact(bundle["topic"], "trusted_claim", claim, float(bundle["confidence"]), source_id)
            self.memory.add_semantic_fact(bundle["topic"], "trusted_claim", claim, float(bundle["confidence"]), source_id)
            # A corroborated knowledge claim is a real lesson: preserve the claim and provenance,
            # not a synthetic experience score/message.
            self.learning.record_approved_lesson({
                "goal": bundle["topic"], "lesson": claim, "score": bundle["confidence"],
                "domain": self.self_directed_learning.detect_domain(bundle["topic"], claim),
                "strategy": "trusted_knowledge", "evidence": json.dumps({
                    "proposal_id": bundle["proposal_id"],
                    "sources": agreement.get("independent_sources", []),
                    "support": agreement.get("support", 0),
                }, ensure_ascii=False), "source": source_id,
            }, bundle["proposal_id"], "approved")
        goals = [g for g in self.self_directed_learning.goals if g.topic == str(bundle["topic"]) ]
        for goal in goals:
            self.self_directed_learning.update_outcome(goal.goal_id, "testing", len(bundle["agreements"]), success=False)
        return {"stored": True, "proposal_id": bundle["proposal_id"], "agreements": len(bundle["agreements"]), "sources": len(bundle["sources"]), "learning_goals_updated": len(goals)}

    @serialized
    def learn_from_internet(self, topic, urls=None, auto=True):
        return self.internet_learning.learn(topic, urls, auto=auto)

    def internet_learning_status(self):
        return self.internet_learning.status()

    @serialized
    def capability_learning_step(self, topic, auto=True):
        """Drive the canonical internet -> experiment -> skill -> transfer loop."""
        return self.capability_learning.learn_topic(topic, auto=auto)

    def capability_learning_status(self):
        return self.capability_learning.status()

    def learn_more(self, limit=5, topics=None):
        """Autonomous bounded learning batch across the foundational curriculum."""
        if topics:
            candidates = [str(x).strip() for x in topics if str(x).strip()]
        else:
            # Keep the curriculum as the source of truth and interleave domains,
            # so a bounded autonomous batch samples breadth instead of taking
            # the first N mathematics topics every time.
            buckets = list(self.self_directed_learning.CURRICULUM.values())
            candidates = []
            width = max((len(bucket) for bucket in buckets), default=0)
            for index in range(width):
                for bucket in buckets:
                    if index < len(bucket):
                        candidates.append(bucket[index])
        candidates = [str(x).strip() for x in candidates if str(x).strip()]
        meta = {"آخرین موضوع فعال چی بود", "ایران", "what was the last active topic"}
        selected=[]; seen=set()
        for topic in candidates:
            key=topic.lower()
            if not topic or key in seen or key in {x.lower() for x in meta}: continue
            seen.add(key); selected.append(topic)
            if len(selected) >= max(1, min(10, int(limit))): break
        results=[]
        for topic in selected:
            try:
                results.append({"topic": topic, "result": self.capability_learning_step(topic, auto=True)})
            except Exception as exc:
                results.append({"topic": topic, "result": {"ok": False, "reason": "cycle_error", "error": str(exc)[:300]}})
        return {
            "ok": True, "requested": len(candidates), "processed": len(results),
            "capability_successes": sum(bool(x["result"].get("capability", {}).get("ok")) for x in results),
            "results": results,
            "status": self.capability_learning_status(),
        }

    def generate_curriculum_learning_inputs(self, batch_size=8):
        before = {g.goal_id for g in self.self_directed_learning.goals}
        goals = self.self_directed_learning.next_curriculum_goals(limit=batch_size)
        created = sum(1 for goal in goals if goal.get("goal_id") not in before)
        return {"ok":True, "goals":goals, "created":created, "reused":len(goals)-created,
                "review_queue":self.chatgpt_review_status()}

    @staticmethod
    def _autonomous_web_goal_allowed(goal):
        topic = str((goal or {}).get("topic", "")).strip().lower()
        gap = str((goal or {}).get("gap", "")).strip().lower()
        objective = str((goal or {}).get("objective", "")).strip().lower()
        # Self/identity dialogue gaps are conversation-state problems, not web-learning topics.
        meta_markers = ("من کیم", "خودت", "تو کی هست", "ایران من", "who am i", "about yourself")
        if any(marker in topic for marker in meta_markers):
            return False
        if gap in {"unknown_answer", "verification_or_confidence_gap"} and objective.startswith("find_supported_answer:"):
            if any(marker in topic for marker in ("من ", "خودت", "تو ")):
                return False
        return bool(topic)

    @serialized
    def learning_tick(self):
        if not self.internet_access.status()["enabled"]:
            return {"ok":False, "reason":"internet_off"}
        rows = self.self_directed_learning.prioritize(50)
        rows.sort(key=lambda row: (str((row.get("goal") or {}).get("gap", "")) == "curriculum", row.get("priority_score", 0)), reverse=True)
        for row in rows:
            goal=row["goal"]
            if goal["status"] not in {"needs_evidence", "conflict"}: continue
            if not self._autonomous_web_goal_allowed(goal): continue
            # InternetLearningEngine performs configured/search/fallback discovery.
            # Do not discard autonomous goals merely because no static source is tagged for them.
            if goal.get("attempts", 0) >= int(self.config.get("learning_max_attempts", 3)): continue
            result=self.learn_from_internet(goal["topic"])
            review_row = result.get("review")
            if review_row:
                proposal_id = review_row.get("proposal_id") if isinstance(review_row, dict) else None
                review_result = self.process_one_chatgpt_learning_review(proposal_id=proposal_id)
                result["online_review"] = review_result
                if proposal_id and review_result.get("proposal_id") != proposal_id:
                    state = "awaiting_review"
                elif review_result.get("ok") and review_result.get("reason") == "reviewed":
                    state = "human_pending" if review_result.get("learn") is True else "needs_evidence"
                else:
                    state = "awaiting_review"
                self.self_directed_learning.update_outcome(goal["goal_id"], state)
            else:
                self.self_directed_learning.update_outcome(goal["goal_id"], "needs_evidence")
            return result
        return {"ok":True,"reason":"no_ready_learning_goal"}

    @serialized
    def maintenance_step(self):
        local = self.autonomous_supervisor_step()
        learning = self.learning_tick()
        mission_work = self.learning_missions.next_unit_fair()
        return {"local": local, "learning": learning, "mission_scheduler": mission_work}

    def observe_knowledge_use(self, question, answer):
        """Record actual reuse of an approved claim; feedback alone cannot award XP."""
        if str(answer).startswith("UNKNOWN:"): return []
        rows=load_critical_json(self.trusted_knowledge_path, [])
        used=[]
        for bundle in rows:
            pid=bundle.get("gate_proposal_id")
            proposal=self.learning_gate.get(pid) if pid else None
            if not proposal or proposal.get("status") != "approved": continue
            claims=[str(a.get("claim", "")) for a in bundle.get("agreements", [])]
            matched=[claim for claim in claims if claim and claim in str(answer)]
            if not matched: continue
            # Exact retrieval is a narrow, reproducible effect, not a claim of general intelligence.
            for claim in matched:
                with self.learning_gate.bypass():
                    outcome=self.effect_learning.evaluate(bundle["topic"], "approved_claim_retrieval", claim, claim,
                        {"verified":True,"score":.9,"source":"approved_claim_in_runtime_answer","effect_observed":True},
                        strategy="knowledge_retrieval",domain="knowledge")
                used.append({"proposal_id":pid,"question":question,"claim":claim,"effect":outcome})
                for goal in self.self_directed_learning.goals:
                    if goal.topic == bundle["topic"]:
                        self.self_directed_learning.record_assessment(goal.goal_id, hashlib.sha256(claim.encode()).hexdigest(), .9, True, kind="retrieval")
        if used: self.events.emit("approved_knowledge_used", {"uses":used})
        return used

    def _chatgpt_review_path(self):
        return self.root / "data" / "chatgpt_reviews.json"

    def _review_decision_journal_path(self):
        return self.root / "data" / "review_decision_journal.json"

    def _review_decision_journal_store(self):
        journal = getattr(self, "_review_decision_journal_instance", None)
        path = self._review_decision_journal_path()
        if journal is None or journal.path != path:
            journal = ReviewDecisionJournal(path)
            self._review_decision_journal_instance = journal
        return journal

    def _sync_review_decision_journal(self):
        """Mirror durable decisions into the observational, tamper-evident journal."""
        rows = load_critical_json(self._chatgpt_review_path(), [])
        return self._review_decision_journal_store().sync(rows)

    def review_decision_journal_status(self):
        """Strict read-only validation; journal state never authorizes learning."""
        return self._review_decision_journal_store().status()

    def review_decision_journal_page(self, limit=50, cursor=None):
        """Return a stable audit page without changing any learning decision."""
        return self._review_decision_journal_store().page(limit, cursor)

    def review_decision_journal_health(self):
        """Dashboard-safe health; strict callers still fail closed on corruption."""
        try:
            return self.review_decision_journal_status()
        except StateCorruptionError:
            return {
                "valid": False,
                "count": None,
                "head_hash": None,
                "source": "corrupt",
                "recovered_from_backup": False,
                "error": "journal_integrity_error",
            }

    def queue_learning_candidate(self, kind, payload, summary=''):
        """Stage a candidate for external review before it reaches LearningGate."""
        def stable(value):
            if isinstance(value, dict):
                return {k: stable(v) for k, v in value.items()
                        if k not in {"time", "timestamp", "created_at", "updated_at", "retrieved_at",
                                     "_external_validation", "episode_id", "attempt"}}
            if isinstance(value, list):
                return [stable(v) for v in value]
            return value
        canonical = json.dumps({"kind": str(kind), "payload": stable(payload)},
                               ensure_ascii=False, sort_keys=True, default=str)
        candidate_id = 'candidate_' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:20]
        now = __import__('datetime').datetime.now().isoformat(timespec='seconds')
        with json_transaction(self._chatgpt_review_path(), []) as rows:
            existing = next((r for r in rows if str(r.get('proposal_id')) == candidate_id), None)
            if existing is not None:
                return dict(existing)
            row = {
                'id': 'learning_' + candidate_id, 'proposal_id': candidate_id,
                'question': str(summary or kind), 'kind': str(kind), 'payload': dict(payload or {}),
                'goal': str((payload or {}).get('goal', '')),
                'review': '', 'review_status': 'not_reviewed', 'status': 'pending',
                'source': 'learning_candidate', 'created_at': now,
            }
            rows.append(row)
            return dict(row)

    def sync_chatgpt_learning_reviews(self, limit=5000, proposal_ids=None):
        """Mirror pending proposals and reconcile interrupted terminal writes.

        Targeted callers may name exact proposal IDs that are older than the
        bounded queue window. This method never calls an external reviewer and
        never approves a pending Gate proposal. A durable reviewer rejection
        may only move a still-pending Gate proposal to the safer rejected state.
        """
        path = self._chatgpt_review_path()
        if proposal_ids is None:
            proposals = self.learning_gate.pending(limit)
        else:
            proposals = []
            seen = set()
            for proposal_id in proposal_ids:
                proposal_id = str(proposal_id)
                if proposal_id in seen:
                    continue
                seen.add(proposal_id)
                proposal = self.learning_gate.get(proposal_id)
                if proposal and proposal.get("status") == "pending":
                    proposals.append(proposal)

        # Snapshot Gate state before taking the reviewer-ledger transaction.
        # This avoids nesting the Gate file lock under the ledger file lock.
        ledger_snapshot = load_critical_json(path, [])
        gate_snapshot = {}
        for row in ledger_snapshot:
            proposal_id = str(row.get("proposal_id", ""))
            if proposal_id and proposal_id not in gate_snapshot:
                gate_snapshot[proposal_id] = self.learning_gate.get(proposal_id)

        reviewer_rejections = set()
        created = 0
        with json_transaction(path, []) as rows:
            existing = {str(r.get("proposal_id")): r for r in rows if r.get("proposal_id")}

            for proposal_id, row in existing.items():
                proposal = gate_snapshot.get(proposal_id)
                if not proposal:
                    continue
                gate_status = proposal.get("status")
                if gate_status in {"approved", "rejected"}:
                    row["status"] = gate_status
                    if (row.get("review_status") == "reviewed"
                            and row.get("chatgpt_decision") == "learn"):
                        row["human_decision"] = gate_status
                        row.setdefault("human_decided_at", proposal.get("updated_at", ""))
                elif (gate_status == "pending"
                        and row.get("review_status") == "reviewed"
                        and row.get("chatgpt_decision") == "reject"
                        and row.get("status") == "rejected"):
                    reviewer_rejections.add(proposal_id)

            for proposal in proposals:
                pid = proposal["proposal_id"]
                if pid in existing:
                    # Repair legacy autonomous rows without discarding decisions.
                    row = existing[pid]
                    row["source"] = "learning_gate"
                    row.setdefault("payload", proposal.get("payload", {}))
                    row.setdefault("kind", proposal.get("kind"))
                    continue
                rows.append({
                    "id": "learning_" + pid, "proposal_id": pid,
                    "question": proposal.get("summary", ""),
                    "kind": proposal.get("kind"), "payload": proposal.get("payload", {}),
                    "goal": str(proposal.get("payload", {}).get("goal", "")),
                    "review": "", "review_status": "not_reviewed", "status": "pending",
                    "source": "learning_gate", "created_at": proposal.get("created_at", ""),
                })
                created += 1
            total = len(rows)
            waiting = sum(r.get("review_status", "not_reviewed") == "not_reviewed" for r in rows)

        # Re-check under LearningGate's own lock; terminal decisions are
        # immutable, so a concurrent human approval cannot be overwritten.
        for proposal_id in reviewer_rejections:
            current = self.learning_gate.get(proposal_id)
            if current and current.get("status") == "pending":
                self.learning_gate.decide(proposal_id, "rejected")

        self._sync_review_decision_journal()
        return {"created": created, "total": total, "not_reviewed": waiting, "reviewed": total-waiting}

    def chatgpt_learning_review_status(self, proposal_id):
        # Only the durable reviewer record is authoritative. Candidate-supplied
        # _external_validation is untrusted input, never approval evidence.
        rows = load_critical_json(self._chatgpt_review_path(), [])
        row = next((r for r in rows if str(r.get("proposal_id")) == str(proposal_id)), None)
        if not row:
            return {"exists": False, "reviewed": False}
        return {"exists": True, "reviewed": row.get("review_status") == "reviewed",
                "review": str(row.get("review", "")), "row": row}

    def chatgpt_review_status(self):
        """Return persisted worker state and queue counts without an API call."""
        path = self._chatgpt_review_path()
        rows = load_critical_json(path, [])
        status = self.chatgpt_review_worker.status()
        status.update({
            "providers": self.reviewer_manager.health() if hasattr(self, "reviewer_manager") else [],
            "waiting": sum(r.get("status") == "WAITING_FOR_REVIEWER" for r in rows),
            "total": len(rows),
            "pending": sum(r.get("status", "pending") in {"pending", "WAITING_FOR_REVIEWER"} and r.get("review_status", "not_reviewed") == "not_reviewed" for r in rows),
            "human_pending": sum(r.get("status") == "human_pending" for r in rows),
            "rejected": sum(r.get("status") == "rejected" for r in rows),
        })
        return status

    def process_one_chatgpt_learning_review(self, proposal_id=None):
        """Run one validation, optionally targeting one durable proposal ID."""
        target_ids = [proposal_id] if proposal_id is not None else None
        if target_ids is None:
            self.sync_chatgpt_learning_reviews()
            result = self.chatgpt_review_worker.process_one()
        else:
            self.sync_chatgpt_learning_reviews(proposal_ids=target_ids)
            result = self.chatgpt_review_worker.process_one(proposal_id=proposal_id)
        if result.get("ok") and result.get("reason") == "reviewed" and result.get("proposal_id"):
            row = self.chatgpt_learning_review_status(result["proposal_id"]).get("row", {})
            payload = row.get("payload", {}) or {}
            if row.get("source") == "learning_candidate" and payload.get("mission_id") and payload.get("unit_id"):
                try:
                    review = json.loads(str(row.get("review", "{}")))
                except (TypeError, ValueError):
                    review = {}
                self.learning_missions.mark_review(
                    payload["mission_id"], payload["unit_id"], result["proposal_id"],
                    "learn" if result.get("learn") else "reject", review.get("reason", ""), source="reviewer")
        if result.get("ok") and result.get("reason") == "reviewed" and result.get("learn") is False:
            proposal_id = result.get("proposal_id")
            review = self.chatgpt_learning_review_status(proposal_id) if proposal_id else {}
            if proposal_id and review.get("row", {}).get("source") == "learning_gate":
                self.learning_gate.decide(proposal_id, "rejected")
        if result.get("ok") and result.get("reason") == "reviewed":
            self._sync_review_decision_journal()
        return result

    def online_learning_review_status(self):
        """Status for the external multi-model reviewer used by online learning."""
        return self.chatgpt_review_status()

    def process_one_online_learning_review(self, proposal_id=None):
        """Review one queued learning candidate, then hand accepted items to the human gate."""
        return self.process_one_chatgpt_learning_review(proposal_id=proposal_id)

    def submit_chatgpt_learning_review(self, proposal_id, review_text):
        """Store a review note only; human approval remains a separate gate."""
        review_text = str(review_text or "").strip()
        if not review_text:
            return {"ok": False, "reason": "empty_review"}
        self.sync_chatgpt_learning_reviews(proposal_ids=[proposal_id])
        with json_transaction(self._chatgpt_review_path(), []) as rows:
            for row in rows:
                if str(row.get("proposal_id")) == str(proposal_id):
                    row["review_note"] = review_text
                    row["review_note_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
                    return {"ok": True, "proposal_id": str(proposal_id), "review_status": row.get("review_status", "not_reviewed")}
        return {"ok": False, "reason": "proposal_not_in_review_queue"}
    def learning_pending(self, limit=50):
        """Return the durable pending proposals for internal learning workflows."""
        return self.learning_gate.pending(limit)

    def learning_pending_page(self, limit=50, cursor=None):
        """Return a stable newest-first page without deleting audit history."""
        return self.learning_gate.pending_page(limit, cursor)

    @staticmethod
    def _human_review_is_pending(row):
        return (
            row.get("proposal_id")
            and row.get("review_status") == "reviewed"
            and row.get("chatgpt_decision") == "learn"
            and row.get("status") == "human_pending"
        )

    @staticmethod
    def _human_candidate_item(review):
        return {
            "proposal_id": str(review.get("proposal_id")),
            "kind": review.get("kind"),
            "payload": review.get("payload", {}),
            "summary": review.get("question", ""),
            "status": "pending",
            "source": "learning_candidate",
            "created_at": review.get("created_at", ""),
        }

    def human_learning_pending_page(self, limit=50, cursor=None):
        """Page reviewer-approved Gate rows and pre-Gate candidates safely.

        Candidate-only rows are paged first using their append-only reviewer
        ledger order. Gate-backed rows then use LearningGate's stable cursor.
        Both cursor types remain resolvable after a row becomes terminal, and
        newer rows never shift an existing continuation page.
        """
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            raise ValueError("limit must be an integer") from None
        if cursor is not None:
            cursor = str(cursor).strip()
            if not cursor:
                raise ValueError("cursor must be a proposal id")
        if limit == 0:
            return {"items": [], "next_cursor": None, "has_more": False}

        reviews = load_critical_json(self._chatgpt_review_path(), [])
        candidate_history = [
            row for row in reviews
            if row.get("source") == "learning_candidate" and row.get("proposal_id")
        ]
        candidate_ids = {str(row.get("proposal_id")) for row in candidate_history}
        gate_ids = {
            str(row.get("proposal_id"))
            for row in reviews
            if row.get("source") != "learning_candidate"
            and self._human_review_is_pending(row)
        }

        items = []
        candidate_has_more = False
        candidate_phase = cursor is None or cursor in candidate_ids
        if cursor is not None and str(cursor).startswith("candidate_") and not candidate_phase:
            raise ValueError("cursor not found")

        if candidate_phase:
            start = len(candidate_history) - 1
            if cursor is not None:
                for index, row in enumerate(candidate_history):
                    if str(row.get("proposal_id")) == cursor:
                        start = index - 1
                        break
                else:
                    raise ValueError("cursor not found")
            for index in range(start, -1, -1):
                row = candidate_history[index]
                if not self._human_review_is_pending(row):
                    continue
                if len(items) >= limit:
                    candidate_has_more = True
                    break
                items.append(self._human_candidate_item(row))

            if len(items) >= limit:
                gate_has_more = False
                if not candidate_has_more and gate_ids:
                    gate_has_more = bool(
                        self.learning_gate.pending_page(
                            1, proposal_ids=gate_ids
                        )["items"]
                    )
                has_more = candidate_has_more or gate_has_more
                return {
                    "items": items,
                    "next_cursor": items[-1]["proposal_id"] if has_more else None,
                    "has_more": has_more,
                }
            gate_cursor = None
        else:
            gate_cursor = cursor

        gate_page = self.learning_gate.pending_page(
            limit - len(items), gate_cursor, proposal_ids=gate_ids
        )
        items.extend(gate_page["items"])
        has_more = gate_page["has_more"]
        return {
            "items": items,
            "next_cursor": items[-1]["proposal_id"] if has_more and items else None,
            "has_more": has_more,
        }

    def human_learning_pending(self, limit=50):
        """Return reviewer-accepted candidates awaiting the human decision."""
        return self.human_learning_pending_page(limit)["items"]

    def learning_history(self, limit=200):
        return self.learning_gate.history(limit)

    def learning_history_page(self, limit=200, cursor=None):
        """Return a stable page of the complete learning audit history."""
        return self.learning_gate.history_page(limit, cursor)

    def _human_learning_pending_count(self):
        """Count the full eligible queue without a fixed proposal scan cap."""
        reviews = load_critical_json(self._chatgpt_review_path(), [])
        candidate_count = sum(
            row.get("source") == "learning_candidate"
            and self._human_review_is_pending(row)
            for row in reviews
        )
        gate_ids = {
            str(row.get("proposal_id"))
            for row in reviews
            if row.get("source") != "learning_candidate"
            and self._human_review_is_pending(row)
        }
        gate_count = 0
        if gate_ids:
            gate_count = len(
                self.learning_gate.pending_page(
                    len(gate_ids), proposal_ids=gate_ids
                )["items"]
            )
        return candidate_count + gate_count

    def learning_status(self):
        status=dict(self.learning_gate.stats())
        status["gate_pending"] = status.get("pending", 0)
        status["pending"] = self._human_learning_pending_count()
        status["candidate_queue"] = self.chatgpt_review_status().get("pending", 0)
        effect=self.effect_learning.stats()
        transfers=self.effect_learning.state.get("transfer_evaluations", [])
        improvements=[float(r.get("improvement", 0) or 0) for r in transfers if "improvement" in r]
        status.update({
            "request_xp": status.get("xp", 0),
            "xp": effect.get("xp", 0),
            "learned_lessons": len(getattr(self.learning, "learned_lessons", []) or []),
            "verified_lessons": sum(1 for x in (getattr(self.learning, "learned_lessons", []) or []) if x.get("status") == "approved"),
            "effect_xp": effect.get("xp", 0),
            "effect_validated": effect.get("validated", 0),
            "transfer_total": len(transfers),
            "transfer_passed": sum(bool(r.get("verified")) and float(r.get("similarity", 0) or 0) >= .25 for r in transfers),
            "improvement_cases": len(improvements),
            "improved_cases": sum(x > 0 for x in improvements),
            "mean_improvement": round(sum(improvements) / len(improvements), 3) if improvements else 0.0,
            "review_decision_journal": self.review_decision_journal_health(),
        })
        return status

    @serialized
    def approve_learning(self, proposal_id, human_confirmed=False, source="api"):
        """Human approval: reviewer-accepted candidate -> LearningGate -> durable apply."""
        if human_confirmed is not True:
            return {"ok":False,"reason":"human_confirmation_required",
                    "message":"تأیید یادگیری فقط با اقدام صریح انسان مجاز است."}
        source = str(source or "human").strip()[:64]
        with file_lock(self.root / "data" / "learning_apply.lock"):
            proposal = self.learning_gate.get(proposal_id)
            if proposal is not None:
                ids = {proposal_id}
                with approval_checkpoint(self, ids):
                    return self._approve_learning(proposal_id, human_source=source)

            review = self.chatgpt_learning_review_status(proposal_id)
            row = review.get("row", {})
            if row.get("source") != "learning_candidate":
                return {"ok": False, "reason": "candidate_not_found"}
            if not review.get("reviewed") or row.get("chatgpt_decision") != "learn":
                return {"ok": False, "reason": "reviewer_acceptance_required"}
            if row.get("status") != "human_pending":
                return {"ok": False, "reason": "candidate_not_human_pending"}
            gate = self.learning_gate.request(row.get("kind"), row.get("payload") or {}, row.get("question", ""))
            if not gate:
                return {"ok": False, "reason": "gate_request_failed"}
            gate_id = gate.get("proposal_id")
            if gate.get("status") == "approved":
                self._set_human_review_status(proposal_id, "approved", gate_id, source)
                payload = row.get("payload", {}) or {}
                if payload.get("mission_id") and payload.get("unit_id"):
                    self.learning_missions.mark_approved(
                        payload["mission_id"], payload["unit_id"], proposal_id, gate_id,
                        approval_source=source)
                return {"ok": True, "proposal": gate, "result": {"already_applied": True},
                        "reviewer_decision": "learn", "candidate_id": proposal_id}
            # A staged learning candidate has a different stable ID from the
            # Gate proposal created only after human approval; checkpoint both.
            with approval_checkpoint(self, {gate_id, proposal_id}):
                result = self._approve_learning(gate_id, review_id=proposal_id, human_source=source)
                if result.get("ok"):
                    result["candidate_id"] = proposal_id
                return result

    def _approve_learning(self, proposal_id, review_id=None, human_source="legacy"):
        proposal=self.learning_gate.get(proposal_id)
        if not proposal: return {"ok":False,"reason":"proposal_not_found"}
        if proposal.get("status") != "pending": return {"ok":False,"reason":"proposal_not_pending","proposal":proposal}
        review_key = review_id or proposal_id
        review = self.chatgpt_learning_review_status(review_key)
        if not review.get("reviewed"):
            return {"ok":False,"reason":"chatgpt_review_required",
                    "message":"ابتدا این درخواست باید توسط ناظر خارجی بررسی و نتیجه بازبینی ثبت شود.",
                    "proposal":proposal}
        decision = review.get("row", {}).get("chatgpt_decision")
        if decision != "learn":
            return {"ok":False,"reason":"reviewer_rejected","proposal":proposal}
        kind=proposal.get("kind"); p=proposal.get("payload") or {}
        with self.learning_gate.bypass():
            if kind == "knowledge.add_fact": result=self.knowledge.add_fact(p["subject"],p["predicate"],p["object"],p.get("confidence",1.0),p.get("source","approved"))
            elif kind == "knowledge.contradict": result=self.knowledge.contradict(p["subject"],p["predicate"],p["object"],p.get("confidence",.7),p.get("source","approved"))
            elif kind == "trusted_knowledge.bootstrap": result=self._apply_trusted_knowledge(proposal)
            elif kind == "learning.goal_request":
                p = dict(p)
                result = self.self_directed_learning.create_goal(p.get("goal_topic", ""), gap="curriculum_request",
                    objective=p.get("objective", ""), priority="medium", domain=p.get("domain", "general"))
            elif kind == "learning.record_experience":
                result=self.learning.record(p["goal"],p["action"],p["result"],p["score"],p.get("intent","general"),p.get("strategy","default"),p.get("domain","general"),p.get("objective",""),p.get("expected_effect",""),p.get("signal_source",""),p.get("evidence",p.get("feedback","")))
                self.learning.record_approved_lesson(p, proposal_id)
            elif kind == "outcome.record": result=self._apply_approved_outcome(p)
            elif kind == "memory.add_semantic_fact": result=self.memory.add_semantic_fact(p["subject"],p["predicate"],p["value"],p.get("confidence",.65),p.get("source","approved"))
            elif kind == "memory.add_lesson":
                result=self.memory.add_lesson(p["goal"],p["lesson"],p.get("confidence",.6),p.get("source","approved"))
                self.learning.record_approved_lesson({"goal":p["goal"],"lesson":p["lesson"],"score":p.get("confidence",.6),"domain":p.get("domain","general"),"strategy":"semantic_memory","source":p.get("source","approved")}, proposal_id)
            elif kind == "procedural.upsert":
                result=self.procedural_memory.upsert(p["name"],p["goal"],p.get("steps",[]),p.get("preconditions",[]),p.get("expected_outcome",""),p.get("verification_conditions",[]),p.get("failure_conditions",[]),p.get("source_experiences",[]),p.get("confidence",.6),p.get("success_rate",0),p.get("procedure_id"))
                lesson_text = f"رویه «{p['name']}» برای «{p['goal']}»: " + "؛ ".join(str(x) for x in (p.get("steps") or []))
                self.learning.record_approved_lesson({"goal":p["goal"],"lesson":lesson_text,"score":p.get("confidence",.6),"domain":p.get("domain","general"),"strategy":"procedure"}, proposal_id)
            elif kind == "procedural.record_outcome": result=self.procedural_memory.record_outcome(p["procedure_id"],p["success"])
            elif kind == "skills.upsert":
                result=self.skills.upsert(p["name"],p["description"],p["domain"],p.get("goal_patterns",[]),p.get("procedure",{}),p.get("preconditions",[]),p.get("required_capabilities",[]),p.get("risk","low"),p.get("confidence",.6),p.get("skill_id"))
                procedure = p.get("procedure") or {}
                lesson_text = f"مهارت «{p['name']}»: {p.get('description','')}"
                if procedure.get("steps"): lesson_text += " مراحل: " + "؛ ".join(str(x) for x in procedure.get("steps", []))
                self.learning.record_approved_lesson({"goal":p.get("name",p.get("domain","general")),"lesson":lesson_text,"score":p.get("confidence",.6),"domain":p.get("domain","general"),"strategy":"skill","evidence":json.dumps(p.get("procedure",{}),ensure_ascii=False)}, proposal_id)
            elif kind == "skills.promote_composition": result=self.skills.promote_composition(p,verified=True)
            elif kind == "skills.execution_outcome": result=self.skills.record_execution(p["skill_id"],p["success"],p.get("verified",True),p.get("reason",""))
            elif kind == "user_model.record_facts": result=self.user_model.record_from_facts(p)
            else: return {"ok":False,"reason":"unsupported_proposal_kind","kind":kind}
        decision=self.learning_gate.decide(proposal_id,"approved")
        self._set_human_review_status(review_key, "approved", proposal_id, human_source)
        if p.get("mission_id") and p.get("unit_id"):
            learned_id = ((result.get("lesson_id") or result.get("id")) if isinstance(result, dict) else result)
            self.learning_missions.mark_approved(
                p["mission_id"], p["unit_id"], review_key, proposal_id,
                learned_id,
                approval_source=human_source)
        self.events.emit("learning_approved",{"proposal_id":proposal_id,"candidate_id":review_key,"kind":kind,"approval_source":human_source})
        return {"ok":True,"proposal":decision,"result":result,
                "reviewer_decision":review.get("row", {}).get("chatgpt_decision", "unknown")}

    def _set_human_review_status(self, proposal_id, status, gate_proposal_id=None, human_source=None):
        updated = False
        with json_transaction(self._chatgpt_review_path(), []) as rows:
            for row in rows:
                if str(row.get("proposal_id")) == str(proposal_id):
                    row["human_decision"] = status
                    row["status"] = status
                    if gate_proposal_id:
                        row["gate_proposal_id"] = str(gate_proposal_id)
                    if human_source:
                        row["human_source"] = str(human_source)[:64]
                    row["human_decided_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
                    updated = True
                    break
        if updated:
            self._sync_review_decision_journal()
        return updated

    @serialized
    def approve_all_learning(self, limit=5000, human_confirmed=False, source="api"):
        limit = max(0, int(limit))
        if human_confirmed is not True:
            return {"ok":False,"reason":"human_confirmation_required","approved":0,
                    "remaining":self.learning_gate.stats().get("pending",0)}
        rows = [] if limit == 0 else self.human_learning_pending(limit)
        results=[]
        skipped=[]
        for row in rows:
            try:
                result=self.approve_learning(row.get("proposal_id"), human_confirmed=True, source=source)
                if result.get("ok"): results.append(result)
                else: skipped.append({"proposal_id":row.get("proposal_id"),"reason":result.get("reason")})
            except Exception as exc:
                skipped.append({"proposal_id":row.get("proposal_id"),"reason":str(exc)})
        return {"ok":True,"approved":len(results),"skipped":skipped,"remaining":self.learning_gate.stats().get("pending",0)}

    def _reject_learning(self, proposal_id, sync_reviews=True):
        review = self.chatgpt_learning_review_status(proposal_id)
        if review.get("row", {}).get("source") == "learning_candidate":
            if review.get("row", {}).get("status") != "human_pending":
                return {"ok":False,"reason":"candidate_not_human_pending"}
            self._set_human_review_status(proposal_id, "rejected")
            payload = review.get("row", {}).get("payload", {}) or {}
            if payload.get("mission_id") and payload.get("unit_id"):
                self.learning_missions.mark_review(payload["mission_id"], payload["unit_id"], proposal_id,
                                                   "reject", "human_rejected", source="human")
            self.events.emit("learning_rejected",{"candidate_id":proposal_id,"kind":review.get("row",{}).get("kind")})
            return {"ok":True,"candidate":review.get("row")}

        proposal = self.learning_gate.get(proposal_id)
        if proposal is None:
            return {"ok":False,"reason":"proposal_not_found"}
        if proposal.get("status") != "pending":
            return {"ok":False,"reason":"proposal_not_pending","proposal":proposal}

        # A direct human rejection must first have a durable reviewer-ledger row.
        # Bulk callers mirror their exact bounded snapshot once before deciding.
        if sync_reviews:
            self.sync_chatgpt_learning_reviews(proposal_ids=[proposal_id])
        result = self.learning_gate.decide(proposal_id, "rejected")
        if result is None:
            return {"ok":False,"reason":"proposal_not_found"}
        if result.get("status") != "rejected":
            return {"ok":False,"reason":"proposal_not_pending","proposal":result}
        self._set_human_review_status(proposal_id, "rejected")
        self.events.emit("learning_rejected",{"proposal_id":proposal_id,"kind":result.get("kind")})
        return {"ok":True,"proposal":result}

    @serialized
    def reject_learning(self, proposal_id):
        return self._reject_learning(proposal_id, sync_reviews=True)

    @serialized
    def reject_all_learning(self, limit=5000):
        limit = max(0, int(limit))
        rows = [] if limit == 0 else self.learning_gate.pending(limit)
        proposal_ids = [row.get("proposal_id") for row in rows if row.get("proposal_id")]
        if proposal_ids:
            self.sync_chatgpt_learning_reviews(proposal_ids=proposal_ids)
        results = []
        skipped = []
        for proposal_id in proposal_ids:
            try:
                result = self._reject_learning(proposal_id, sync_reviews=False)
                if result.get("ok"):
                    results.append(result)
                else:
                    skipped.append({"proposal_id":proposal_id,"reason":result.get("reason")})
            except Exception as exc:
                skipped.append({"proposal_id":proposal_id,"reason":str(exc)})
        return {"ok":True,"rejected":len(results),"skipped":skipped,
                "remaining":self.learning_gate.stats().get("pending",0)}

    def health(self):
        return self.brain.health()

    def metrics(self):
        metrics = self.orchestrator.metrics.snapshot()
        outcomes = list(getattr(self.outcome_learning, "records", []) or [])
        verified = [row for row in outcomes if row.get("verified")]
        failed = [row for row in outcomes if not row.get("verified") or float(row.get("score", 0)) < .55]
        cap = self.capability_learning.status() if getattr(self, "capability_learning", None) else {}
        skills = list(getattr(self.skills, "skills", []) or [])
        executions = sum(int(row.get("execution_count", 0)) for row in skills)
        reuse_success = sum(int(row.get("successful_execution_count", 0)) for row in skills)
        duplicate_keys = [(row.get("goal"), row.get("action"), str(row.get("result", ""))[:250]) for row in outcomes]
        duplicate_rate = 1 - (len(set(duplicate_keys)) / len(duplicate_keys)) if duplicate_keys else 0.0
        metrics.update({
            "learning_attempts": len(outcomes) + int(cap.get("experiments", 0)),
            "verified_learning": len(verified),
            "failed_learning": len(failed) + int(cap.get("failures", 0)),
            "repair_success_rate": round(max(0, int(cap.get("repairs", 0)) - int(cap.get("failures", 0))) / max(1, int(cap.get("repairs", 0))), 3),
            "transfer_success_rate": round(int(cap.get("transfers", 0)) / max(1, int(cap.get("successes", 0))), 3),
            "generalization_rate": round(int(cap.get("transfers", 0)) / max(1, int(cap.get("skills_promoted", 0))), 3),
            "skill_reuse_success": round(reuse_success / max(1, executions), 3),
            "skill_regression_rate": round(sum(int(row.get("failed_execution_count", 0)) for row in skills) / max(1, executions), 3),
            "knowledge_to_skill_rate": round(int(cap.get("skills_promoted", 0)) / max(1, int(cap.get("successes", 0))), 3),
            "duplicate_learning_rate": round(duplicate_rate, 3),
            "source_agreement_rate": round(sum(1 for row in outcomes if row.get("verification_source")) / max(1, len(outcomes)), 3),
        })
        return metrics

    def cognitive_snapshot(self, text):
        # Snapshot is observational: execute exactly one canonical turn, then read its state.
        self.cognitive_system.turn(str(text))
        output = self.cognitive_system.unified_output()
        output["world"] = self.world.snapshot()
        output["knowledge"] = self.knowledge.stats()
        output["learning"] = self.learning.stats()
        output["memory"] = self.memory.stats()
        output["prediction"] = self.prediction.calibration()
        return output

    @serialized
    def benchmark_run(self):
        return self.benchmark.run(self.brain.language, self.provider, self.brain,
                                  self.orchestrator.planner, self.kernel).__dict__

    @serialized
    def roadmap_benchmark(self):
        from self.roadmap_benchmark import PersianRoadmapBenchmark
        return PersianRoadmapBenchmark().run(self)

    @serialized
    def scenario_benchmark(self, limit=None):
        from self.scenario_benchmark import PersianScenarioBenchmark
        return PersianScenarioBenchmark().run(self, limit=limit)

    def evaluate(self):
        return {"compile": self.evaluator.compile_all(), "benchmark": self.benchmark_run(),
                "world": self.world.snapshot(), "learning": self.learning.stats(),
                "prediction": self.prediction.calibration()}

    def decide(self, text):
        return self.orchestrator.explain_decision(text)

    def reflect(self, text, answer, score):
        return self.reflector.reflect(text, answer, score).__dict__

    def conversation_snapshot(self):
        return self.dialogue.snapshot()

    def conversation_trace(self):
        return self.dialogue.trace()

    def create_task(self, description, goal_id=None, **kwargs):
        task = self.tasks.create(description, goal_id=goal_id, **kwargs)
        self.tasks.transition(task.task_id, TaskStatus.READY.value, "task created")
        self.events.emit("task_created", {"task_id": task.task_id, "description": description})
        return self.tasks.get(task.task_id)

    @serialized
    def execute_verified_action(self, task_id, tool_name, expected_effect, evidence=None, **kwargs):
        self.tasks.transition(task_id, TaskStatus.RUNNING.value, "action execution")
        action = self.actions.execute(task_id, tool_name, expected_effect, **kwargs)
        observation = self.observer.observe(action, evidence=evidence or [])
        verification = self.verifier.verify(observation)
        self.tasks.transition(task_id, TaskStatus.SUCCESS.value if verification.success else TaskStatus.FAILED.value,
                              verification.reason)
        return action, observation, verification

    def fail_and_replan(self, task_id, reason, category="verification", failed_assumption="", alternatives=None):
        diagnosis = self.failure.diagnose(reason, category)
        self.events.emit("failure_diagnosed", {
            "task_id": task_id, "reason": str(reason), "category": str(category),
            "diagnosis": diagnosis.__dict__ if hasattr(diagnosis, "__dict__") else str(diagnosis),
        })
        decision = self.replanner.replan(task_id, reason, failed_assumption, alternatives or [])
        self.events.emit("plan_replanned", {
            "task_id": task_id, "selected": decision.selected,
            "reason": str(reason), "category": str(category),
        })
        self.events.emit("replan_decision", {"task_id": task_id, "selected": decision.selected, "reason": reason})
        return diagnosis, decision

    def _record_transition(self, task_id, action, observation, verification):
        try:
            self.transition_recorder.record(
                task_id,
                action.__dict__ if hasattr(action, "__dict__") else dict(action),
                observation.__dict__ if hasattr(observation, "__dict__") else dict(observation),
                verification.__dict__ if hasattr(verification, "__dict__") else dict(verification),
            )
        except Exception:
            pass

    def execute_recoverable_task(self, description, primary, alternative, expected_effect, **kwargs):
        task = self.create_task(description)
        plan = self.orchestrator.planner.build(description)
        def attempt(tool, phase):
            self.tasks.transition(task["task_id"], TaskStatus.RUNNING.value, phase)
            action = self.actions.execute(task["task_id"], tool, expected_effect, **kwargs)
            obs = self.observer.observe(action, actual=action.result,
                evidence=[{"source": phase, "tool": tool, "actual": action.result}])
            verification = self.verifier.verify(obs,
                predicate=lambda item: str(item.actual).strip() == str(expected_effect).strip())
            self.prediction.record(tool, verification.success, phase, expected_effect)
            self._record_transition(task["task_id"], action, obs, verification)
            return action, verification
        action, primary_v = attempt(primary, "primary attempt")
        if primary_v.success:
            self.tasks.transition(task["task_id"], TaskStatus.SUCCESS.value, primary_v.reason)
            return {"task": self.tasks.get(task["task_id"]), "plan": plan,
                    "primary": primary_v.__dict__, "replan": None}
        diagnosis, decision = self.fail_and_replan(task["task_id"], primary_v.reason,
            "verification", expected_effect, [alternative])
        plan = self.orchestrator.planner.replan(plan, 1, primary_v.reason)
        action2, alt_v = attempt(alternative, "alternative attempt")
        self.tasks.transition(task["task_id"], TaskStatus.SUCCESS.value if alt_v.success else TaskStatus.FAILED.value,
                              alt_v.reason)
        self.events.emit("recovery_completed", {
            "task_id": task["task_id"], "success": bool(alt_v.success),
            "selected": alternative, "reason": str(alt_v.reason or ""),
        })
        return {"task": self.tasks.get(task["task_id"]), "plan": plan,
                "primary": primary_v.__dict__, "diagnosis": diagnosis.__dict__,
                "replan": decision.__dict__, "alternative": alt_v.__dict__}
    @serialized
    def execute_verified_goal(self, goal, primary, alternative=None, expected_effect="", kwargs=None):
        kwargs = dict(kwargs or {})
        goal_record = self.goals.add(str(goal))
        candidates = self.skills.discover(goal, "task", 8)
        composition = self.skills.compose(goal, candidates, {"evidence": True}, 8)
        if composition and len(composition.get("steps", [])) >= 2:
            return self._execute_composed_goal(composition, expected_effect, kwargs)
        lesson = self.outcome_learning.lesson(goal, "task")
        # Task execution consults the same CognitiveSystem learning brain as dialogue.
        guidance = self.cognitive_system.guidance(goal, "task", "task")
        choices = [primary] + ([alternative] if alternative else [])
        experience = self.outcome_learning.recommend_action(goal, choices, "task")
        if not isinstance(experience, dict):
            experience = {}
        if not experience.get("selected") and guidance.get("recommended_strategy"):
            experience["strategy"] = guidance["recommended_strategy"]
            self.events.emit("learning_guidance_applied", {
                "goal": goal, "domain": "task",
                "strategy": guidance["recommended_strategy"],
                "failure_signal": bool(guidance.get("failure_signal")),
            })
        transfer_candidates = self.skills.retrieve_transfer(goal, "task", limit=4)
        transfer_skill = transfer_candidates[0] if transfer_candidates else None
        plan = self.orchestrator.planner.build(goal, experience=experience)
        task = self.create_task(goal)
        selected = experience.get("selected") if isinstance(experience, dict) else primary
        if selected not in choices:
            selected = primary
        if transfer_skill:
            steps = (transfer_skill.get("procedure") or {}).get("steps") or []
            transferred_action = steps[0].get("action") if steps and isinstance(steps[0], dict) else None
            if transferred_action in choices:
                selected = transferred_action
                plan.strategy = f"skill-transfer:{selected}"
                self.events.emit("skill_transfer_consulted", {
                    "task_id": task["task_id"], "goal": goal,
                    "skill_id": transfer_skill.get("skill_id"),
                    "selected": selected, "applied": True,
                })
        if isinstance(experience, dict) and experience.get("selected"):
            self.events.emit("strategy_reused", {
                "task_id": task["task_id"], "goal": goal,
                "selected": selected, "source": "outcome_backed_learning",
            })
        def attempt(tool, phase):
            self.tasks.transition(task["task_id"], TaskStatus.RUNNING.value, phase)
            action = self.actions.execute(task["task_id"], tool, expected_effect, **kwargs)
            obs = self.observer.observe(action, actual=action.result,
                evidence=[{"source": phase, "tool": tool, "actual": action.result}])
            verification = self.verifier.verify(obs,
                predicate=lambda item: str(item.actual).strip() == str(expected_effect).strip())
            self.prediction.record(tool, verification.success, phase, expected_effect)
            self._record_transition(task["task_id"], action, obs, verification)
            return action, verification
        action, verification = attempt(selected, "primary")
        if verification.success:
            self.tasks.transition(task["task_id"], TaskStatus.SUCCESS.value, verification.reason)
            self.goals.complete(goal_record["id"])
            result = self.outcome_learning.record_outcome(
                goal, selected, str(action.result), expected_effect,
                {"verified": True, "source": "task_verifier", "score": 1.0},
                strategy=lesson.get("strategy", "evidence-first"), domain="task",
                episode_id=task["task_id"], phase="primary", attempt=1,
            )
            return {"task": self.tasks.get(task["task_id"]), "plan": plan,
                    "primary": verification.__dict__, "alternative": None, "learning": result,
                    "success": True}
        if not alternative:
            self.tasks.transition(task["task_id"], TaskStatus.FAILED.value, verification.reason)
            return {"task": self.tasks.get(task["task_id"]), "plan": plan,
                    "primary": verification.__dict__, "alternative": None, "success": False}
        other = alternative if selected == primary else primary
        primary_learning = self.outcome_learning.record_outcome(
            goal, selected, str(action.result), expected_effect,
            {"verified": True, "source": "task_verifier", "score": 0.0},
            strategy=lesson.get("strategy", "primary-then-replan"), domain="task",
            episode_id=task["task_id"], phase="primary", attempt=1,
        )
        diagnosis, decision = self.fail_and_replan(task["task_id"], verification.reason,
            "verification", expected_effect, [other])
        plan = self.orchestrator.planner.replan(plan, 1, verification.reason)
        action2, verification2 = attempt(other, "alternative")
        self.tasks.transition(task["task_id"], TaskStatus.SUCCESS.value if verification2.success else TaskStatus.FAILED.value,
                              verification2.reason)
        if verification2.success:
            self.goals.complete(goal_record["id"])
        result = None
        if verification2.success:
            result = self.outcome_learning.record_outcome(
                goal, other, str(action2.result), expected_effect,
                {"verified": True, "source": "task_verifier", "score": 1.0},
                strategy=lesson.get("strategy", "primary-then-replan"), domain="task",
                episode_id=task["task_id"], phase="alternative", attempt=2,
            )
        return {"task": self.tasks.get(task["task_id"]), "plan": plan,
                "primary": verification.__dict__, "diagnosis": diagnosis.__dict__,
                "replan": decision.__dict__, "alternative": verification2.__dict__,
                "learning": result, "primary_learning": primary_learning,
                "success": bool(verification2.success)}

    def _execute_composed_goal(self, composition, final_expected, kwargs):
        goal = composition.get("goal", "")
        task = self.create_task(goal)
        plan = self.orchestrator.planner.build(goal)
        plan.strategy = "skill-composition"
        results = []
        for step in composition["steps"]:
            expected = step.get("expected_effect") or final_expected
            self.tasks.transition(task["task_id"], TaskStatus.RUNNING.value, f"composition step {step['order']}")
            action = self.actions.execute(task["task_id"], step["action"], expected, **kwargs)
            observation = self.observer.observe(action, actual=action.result,
                evidence=[{"source": "composed-skill-step", "tool": step["action"]}])
            verification = self.verifier.verify(observation,
                predicate=lambda item, exp=expected: str(item.actual).strip() == str(exp).strip())
            results.append({"step": step, "action": action, "verification": verification})
            self.events.emit("skill_composition_step", {
                "task_id": task["task_id"], "order": step.get("order"),
                "action": step.get("action"), "success": bool(verification.success),
            })
            if step.get("skill_id"):
                self.skills.record_execution(step["skill_id"], verification.success, verified=True,
                                             reason=str(verification.reason or ""))
            if not verification.success:
                self.tasks.transition(task["task_id"], TaskStatus.FAILED.value, verification.reason)
                self.events.emit("skill_composition_failed", {
                    "task_id": task["task_id"], "goal": goal,
                    "failed_step": step.get("order"), "reason": str(verification.reason or ""),
                })
                return {"task": self.tasks.get(task["task_id"]), "composition": composition,
                        "steps": results, "success": False, "plan": plan,
                        "plan_strategy": plan.strategy}
        self.tasks.transition(task["task_id"], TaskStatus.SUCCESS.value,
                              "all composed steps independently verified")
        # The composition itself has just been independently verified step-by-step;
        # persist that verified artifact immediately. Autonomous promotion remains gated elsewhere.
        gate_ctx = self.learning_gate.bypass() if self.learning_gate is not None else None
        if gate_ctx is not None:
            gate_ctx.__enter__()
        try:
            persisted = self.skills.promote_composition(composition, verified=True)
            higher = self.skills.promote_composition_as_skill(persisted, domain="task") if persisted else None
        finally:
            if gate_ctx is not None:
                gate_ctx.__exit__(None, None, None)
        self.events.emit("skill_composition_completed", {
            "task_id": task["task_id"], "goal": goal,
            "steps": len(results), "skill_ids": composition.get("skill_ids", []),
        })
        return {"task": self.tasks.get(task["task_id"]), "composition": composition,
                "steps": results, "success": True, "plan": plan, "plan_strategy": plan.strategy,
                "persisted_composition": persisted, "higher_order_skill": higher}
    def learn_procedure_skill(self, goal, strategy, source_experiences=None,
                              domain="general", expected_effect=""):
        result = self.skills.learn_from_experience(goal, strategy,
            source_experiences or [], domain)
        if isinstance(result, dict) and result.get("skill"):
            result["skill"].setdefault("procedure", {})["expected_outcome"] = str(expected_effect)
            self.skills._save()
        return result

    @serialized
    def autonomous_step(self):
        return self.autonomy.step()

    @serialized
    def autonomous_run(self, cycles=1):
        return self.autonomy.run(cycles)

    @serialized
    def autonomous_supervisor_step(self):
        return self.autonomous_supervisor.step()

    @serialized
    def autonomous_supervisor_run(self, cycles=1):
        return self.autonomous_supervisor.run(cycles)

    def autonomous_supervisor_snapshot(self):
        return self.autonomous_supervisor.snapshot()

    def close(self):
        with self.__dict__.setdefault('_mutation_lock', threading.RLock()):
            self._close_resources()

    def _close_resources(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        try:
            self.autonomy.stop()
        except Exception:
            pass
        try:
            self.autonomous_supervisor.stop()
        except Exception:
            pass
        try:
            if getattr(self, "cognitive_system", None) is not None:
                self.cognitive_system.close()
        except Exception:
            pass
        try:
            self.memory.close()
        except Exception:
            pass
        ownership = getattr(self, '_ownership', None)
        if ownership is not None:
            ownership.close()
            self._ownership = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def architecture(self):
        return self.cognitive_system.architecture_contract()

    def inspect(self):
        snapshot = dict(self.cognitive_system.inspect())
        snapshot["review_decision_journal"] = self.review_decision_journal_health()
        return snapshot
    def _handle_command(self, text):
        import shlex
        parts = shlex.split(text)
        if not parts:
            return ""
        if parts[0] in {"/internet", "/network"}:
            action = parts[1].lower() if len(parts) > 1 else "status"
            if action in {"on", "enable", "روشن"}:
                result = self.internet_access.enable()
                self.events.emit("internet_access_changed", result)
                return json.dumps(result, ensure_ascii=False)
            if action in {"off", "disable", "خاموش"}:
                result = self.internet_access.disable()
                self.events.emit("internet_access_changed", result)
                return json.dumps(result, ensure_ascii=False)
            return json.dumps(self.internet_access.status(), ensure_ascii=False)
        if parts[0] in {"/learnweb", "/learn-internet"}:
            topic = str(parts[1]).strip() if len(parts) > 1 else ""
            urls = parts[2:] if len(parts) > 2 else None
            if not topic: return "usage=/learnweb <topic> [url ...]"
            return json.dumps(self.learn_from_internet(topic, urls), ensure_ascii=False)
        if parts[0] in {"/learnstatus", "/learning-status"}:
            return json.dumps(self.internet_learning_status(), ensure_ascii=False)
        if parts[0] in {"/learncap", "/learn-capability"}:
            topic = str(parts[1]).strip() if len(parts) > 1 else ""
            if not topic: return "usage=/learncap <topic>"
            return json.dumps(self.capability_learning_step(topic), ensure_ascii=False)
        if parts[0] in {"/capstatus", "/capability-status"}:
            return json.dumps(self.capability_learning_status(), ensure_ascii=False)
        if parts[0] in {"/learn", "/learning"}:
            if len(parts) < 2 or parts[1] in {"pending", "list"}:
                rows=self.human_learning_pending()
                return "no_pending_learning" if not rows else json.dumps(rows,ensure_ascii=False)
            if parts[1] in {"approve", "reject"} and len(parts) >= 3:
                result=self.approve_learning(parts[2], human_confirmed=True, source="command") if parts[1]=="approve" else self.reject_learning(parts[2])
                return json.dumps(result,ensure_ascii=False)
            return "usage=/learn pending | /learn approve <proposal_id> | /learn reject <proposal_id>"
        if parts[0] == "/run":
            try:
                tool = parts[parts.index("--tool") + 1]
                expected = parts[parts.index("--expected") + 1]
            except (ValueError, IndexError):
                return "task=failed verified=False"
            alternative = None
            if "--alternative" in parts:
                try:
                    alternative = parts[parts.index("--alternative") + 1]
                except IndexError:
                    pass
            goal_parts = []
            for item in parts[1:]:
                if item.startswith("--"):
                    break
                goal_parts.append(item)
            goal = " ".join(goal_parts)
            result = self.execute_verified_goal(goal, tool, alternative, expected)
            verified = bool(result.get("alternative", {}).get("success") if result.get("alternative")
                            else result.get("primary", {}).get("success"))
            status = "success" if verified else "failed"
            self.events.emit("verified_task_completed", {"task_id": result["task"]["task_id"],
                "phase": "command", "success": verified})
            return f"task={status} verified={verified}"
        return "unknown_command"
