"""Canonical local runtime for the IRAN cognitive architecture."""
from pathlib import Path
import json

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
from learning.self_directed import SelfDirectedLearning
from learning.trusted_knowledge import TrustedKnowledgeBootstrap
from learning.procedural_memory import ProceduralMemory
from learning.skill_system import SkillSystem
from learning.internet_learning import InternetLearningEngine
from learning.capability_learning import CapabilityLearningEngine
from providers.factory import create_provider
from runtime.events import EventLog
from runtime.goals import GoalStore
from runtime.scheduler import Scheduler
from runtime.runner import BackgroundRunner
from runtime.task_runtime import TaskRuntime, TaskStatus
from runtime.conversation_router import ConversationRouter
from security.policy import SecurityPolicy
from security.learning_gate import LearningGate
from security.internet_access import InternetAccessManager
from tools.builtin import build_registry
from self.evaluator import Evaluator
from self.benchmark import CognitiveBenchmark
from self.improvement_loop import SelfImprovementLoop


class IranRuntime:
    """Single runtime composition root; ordinary turns enter CognitiveSystem."""

    def __init__(self, root):
        self.root = Path(root)
        self.config = json.loads((self.root / "config.json").read_text(encoding="utf-8-sig"))
        self.provider = create_provider(self.config)
        self.learning_gate = LearningGate(self.root / "data/learning_proposals.json")
        self.trusted_knowledge = TrustedKnowledgeBootstrap()
        self.self_directed_learning = SelfDirectedLearning(self.root / "data/learning_goals.json")
        self.trusted_knowledge_path = self.root / "data/trusted_knowledge.json"
        self.memory = Memory(self.root / self.config["memory"]["db"], gate=self.learning_gate)
        self.events = EventLog(self.root / self.config["runtime"]["event_log"])
        self.goals = GoalStore(self.root / self.config["runtime"].get("goals", "data/goals.json"))
        self.internet_access = InternetAccessManager(self.root / "data/internet_access.json")
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
        self.observer = ObservationEngine(self.events)
        self.verifier = VerificationEngine(self.events)
        self.failure = FailureIntelligence()
        self.replanner = Replanner(self.events)
        self.adaptive_execution = AdaptiveExecutionPolicy(max_replans=1)
        self.transition_recorder = TransitionRecorder(self.world)
        from core.learning_loop import OutcomeBackedLearning
        self.outcome_learning = OutcomeBackedLearning(
            self.root / "data/verified_outcomes.json", self.learning, self.learning_gate)
        self.procedural_memory = ProceduralMemory(self.root / "data/procedures.json", gate=self.learning_gate)
        self.skills = SkillSystem(self.root / "data/skills.json", self.procedural_memory, gate=self.learning_gate)
        self.user_model = UserModel(self.memory, self.knowledge, "IRAN", gate=self.learning_gate)
        self.internet_learning = InternetLearningEngine(self)
        self.capability_learning = CapabilityLearningEngine(self)
        self.language_intelligence = PersianIntelligence(self.brain.language)
        self.conversation_router = ConversationRouter(self)
        from core.orchestrator import Orchestrator
        self.orchestrator = Orchestrator(
            self.agent, self.memory, self.events, self.registry, self.policy,
            self.goals, self.evaluator)
        self.orchestrator._user_model = self.user_model
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

    def handle(self, text):
        # One public ingress: the CognitiveSystem owns routing; runtime is infrastructure.
        return self.cognitive_system.dispatch(text)

    def _apply_approved_outcome(self, p):
        outcome=self.outcome_learning
        outcome.records.append(dict(p)); outcome._save()
        result = {"recorded": True, "verified": bool(p.get("verified")), "learned": False}
        if bool(p.get("verified")) and self.learning is not None:
            learned = self.learning.record(
                p.get("goal",""), p.get("action",""), p.get("result",""), p.get("score",0),
                intent="verified_outcome", strategy=p.get("strategy","default"), domain=p.get("domain","general"),
            )
            result.update(learned or {})
            result["learned"] = True
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
        gated = self.learning_gate.request(
            "trusted_knowledge.bootstrap", proposal,
            f"Trusted knowledge bootstrap: {topic}",
        )
        return gated or proposal

    def _apply_trusted_knowledge(self, proposal):
        rows = []
        path = self.trusted_knowledge_path
        try:
            rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except Exception:
            rows = []
        if not isinstance(rows, list): rows = []
        payload = proposal.get("payload") or proposal
        bundle = {
            "proposal_id": payload.get("proposal_id"),
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
            atomic_write_json(path, rows[-1000:])
        for agreement in bundle["agreements"]:
            claim = str(agreement.get("claim", "")).strip()
            if not claim: continue
            self.knowledge.add_fact(bundle["topic"], "trusted_claim", claim, float(bundle["confidence"]), "trusted_knowledge:" + str(bundle["proposal_id"]))
            self.memory.add_semantic_fact(bundle["topic"], "trusted_claim", claim, float(bundle["confidence"]), "trusted_knowledge:" + str(bundle["proposal_id"]))
        goals = [g for g in self.self_directed_learning.goals if g.topic == str(bundle["topic"]) ]
        for goal in goals:
            self.self_directed_learning.update_outcome(goal.goal_id, "testing", len(bundle["agreements"]), success=False)
        return {"stored": True, "proposal_id": bundle["proposal_id"], "agreements": len(bundle["agreements"]), "sources": len(bundle["sources"]), "learning_goals_updated": len(goals)}

    def learn_from_internet(self, topic, urls=None, auto=True):
        return self.internet_learning.learn(topic, urls, auto=auto)

    def internet_learning_status(self):
        return self.internet_learning.status()

    def capability_learning_step(self, topic, auto=True):
        """Drive the canonical internet -> experiment -> skill -> transfer loop."""
        return self.capability_learning.learn_topic(topic, auto=auto)

    def capability_learning_status(self):
        return self.capability_learning.status()

    def learning_pending(self, limit=50):
        return self.learning_gate.pending(limit)

    def learning_history(self, limit=200):
        return self.learning_gate.history(limit)

    def learning_status(self):
        return self.learning_gate.stats()

    def approve_learning(self, proposal_id):
        proposal=self.learning_gate.get(proposal_id)
        if not proposal: return {"ok":False,"reason":"proposal_not_found"}
        if proposal.get("status") != "pending": return {"ok":False,"reason":"proposal_not_pending","proposal":proposal}
        kind=proposal.get("kind"); p=proposal.get("payload") or {}
        with self.learning_gate.bypass():
            if kind == "knowledge.add_fact": result=self.knowledge.add_fact(p["subject"],p["predicate"],p["object"],p.get("confidence",1.0),p.get("source","approved"))
            elif kind == "trusted_knowledge.bootstrap": result=self._apply_trusted_knowledge(proposal)
            elif kind == "learning.record_experience": result=self.learning.record(p["goal"],p["action"],p["result"],p["score"],p.get("intent","general"),p.get("strategy","default"),p.get("domain","general"))
            elif kind == "outcome.record": result=self._apply_approved_outcome(p)
            elif kind == "memory.add_semantic_fact": result=self.memory.add_semantic_fact(p["subject"],p["predicate"],p["value"],p.get("confidence",.65),p.get("source","approved"))
            elif kind == "memory.add_lesson": result=self.memory.add_lesson(p["goal"],p["lesson"],p.get("confidence",.6),p.get("source","approved"))
            elif kind == "procedural.upsert": result=self.procedural_memory.upsert(p["name"],p["goal"],p.get("steps",[]),p.get("preconditions",[]),p.get("expected_outcome",""),p.get("verification_conditions",[]),p.get("failure_conditions",[]),p.get("source_experiences",[]),p.get("confidence",.6),p.get("success_rate",0),p.get("procedure_id"))
            elif kind == "procedural.record_outcome": result=self.procedural_memory.record_outcome(p["procedure_id"],p["success"])
            elif kind == "skills.upsert": result=self.skills.upsert(p["name"],p["description"],p["domain"],p.get("goal_patterns",[]),p.get("procedure",{}),p.get("preconditions",[]),p.get("required_capabilities",[]),p.get("risk","low"),p.get("confidence",.6),p.get("skill_id"))
            elif kind == "skills.promote_composition": result=self.skills.promote_composition(p,verified=True)
            elif kind == "skills.execution_outcome": result=self.skills.record_execution(p["skill_id"],p["success"],p.get("verified",True),p.get("reason",""))
            elif kind == "user_model.record_facts": result=self.user_model.record_from_facts(p)
            else: return {"ok":False,"reason":"unsupported_proposal_kind","kind":kind}
        decision=self.learning_gate.decide(proposal_id,"approved")
        self.events.emit("learning_approved",{"proposal_id":proposal_id,"kind":kind})
        return {"ok":True,"proposal":decision,"result":result}

    def reject_learning(self, proposal_id):
        result=self.learning_gate.decide(proposal_id,"rejected")
        if result is None: return {"ok":False,"reason":"proposal_not_found"}
        self.events.emit("learning_rejected",{"proposal_id":proposal_id,"kind":result.get("kind")})
        return {"ok":True,"proposal":result}

    def health(self):
        return self.brain.health()

    def metrics(self):
        return self.orchestrator.metrics.snapshot()

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

    def benchmark_run(self):
        return self.benchmark.run(self.brain.language, self.provider, self.brain,
                                  self.orchestrator.planner, self.kernel).__dict__

    def roadmap_benchmark(self):
        from self.roadmap_benchmark import PersianRoadmapBenchmark
        return PersianRoadmapBenchmark().run(self)

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

    def autonomous_step(self):
        return self.autonomy.step()

    def autonomous_run(self, cycles=1):
        return self.autonomy.run(cycles)

    def autonomous_supervisor_step(self):
        return self.autonomous_supervisor.step()

    def autonomous_supervisor_run(self, cycles=1):
        return self.autonomous_supervisor.run(cycles)

    def autonomous_supervisor_snapshot(self):
        return self.autonomous_supervisor.snapshot()

    def close(self):
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
            self.memory.close()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def architecture(self):
        return self.cognitive_system.architecture_contract()

    def inspect(self):
        return self.cognitive_system.inspect()
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
                rows=self.learning_pending()
                return "no_pending_learning" if not rows else json.dumps(rows,ensure_ascii=False)
            if parts[1] in {"approve", "reject"} and len(parts) >= 3:
                result=self.approve_learning(parts[2]) if parts[1]=="approve" else self.reject_learning(parts[2])
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
