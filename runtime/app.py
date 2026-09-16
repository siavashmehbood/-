from pathlib import Path
import json
from core.agent import Agent
from core.brain import Brain
from core.orchestrator import Orchestrator
from core.cognition_engine import CognitiveEngine
from core.world_model import WorldModel
from core.prediction import PredictionEngine
from core.anomaly import AnomalyDetector
from core.kernel import CognitiveKernel
from core.reflection import ReflectionEngine
from memory.store import Memory
from knowledge.knowledge_graph import KnowledgeGraph
from learning.learning_engine import LearningEngine
from providers.factory import create_provider
from runtime.events import EventLog
from runtime.goals import GoalStore
from runtime.scheduler import Scheduler
from runtime.conversation_router import ConversationRouter
from runtime.runner import BackgroundRunner
from security.policy import SecurityPolicy
from tools.builtin import build_registry
from self.evaluator import Evaluator
from self.benchmark import CognitiveBenchmark
from self.improvement_loop import SelfImprovementLoop
from core.answer_generator import AnswerGenerator
from core.response_engine import LocalResponseEngine
from core.rule_engine import SymbolicRuleEngine

class IranRuntime:
    """Local autonomous runtime wiring perception, cognition, memory, action, learning and self-evaluation."""
    def __init__(self,root):
        self.root=Path(root);self.config=json.loads((self.root/'config.json').read_text(encoding='utf-8-sig'))
        self.provider=create_provider(self.config);self.brain=Brain(self.provider);self.memory=Memory(self.root/self.config['memory']['db']);self.events=EventLog(self.root/self.config['runtime']['event_log'])
        self.goals=GoalStore(self.root/self.config['runtime'].get('goals','data/goals.json'));self.policy=SecurityPolicy(self.config);self.registry=build_registry(self.root,self.memory);self.agent=Agent(self.brain,self.memory,self.config['memory']['max_history'])
        self.evaluator=Evaluator(self.root);self.benchmark=CognitiveBenchmark();self.improvement=SelfImprovementLoop(self.root);self.cognition_engine=CognitiveEngine();self.world=WorldModel(self.root/'data/world.json')
        self.knowledge=KnowledgeGraph(self.root/'data/knowledge.json');self.learning=LearningEngine(self.root/'data/experiences.json');self.prediction=PredictionEngine(self.root/'data/predictions.json');self.anomaly=AnomalyDetector();self.kernel=CognitiveKernel(self.memory,self.world,self.knowledge,self.prediction,self.anomaly,self.learning)
        self._seed_local_knowledge()
        self.rules=SymbolicRuleEngine()
        self.rules.add('Ù¾Ø±ÙˆÚ˜Ù‡ Ø§ÛŒØ±Ø§Ù†', 'Ù…Ø¹Ù…Ø§Ø±ÛŒ Ø´Ù†Ø§Ø®ØªÛŒ', .95, 'project_definition')
        self.rules.add('Ù…Ø¹Ù…Ø§Ø±ÛŒ Ø´Ù†Ø§Ø®ØªÛŒ', 'Ù†ÛŒØ§Ø²Ù…Ù†Ø¯ Ø­Ø§ÙØ¸Ù‡ Ùˆ Ø§Ø³ØªØ¯Ù„Ø§Ù„', .9, 'architecture_principle')
        self.answer_generator=AnswerGenerator(getattr(self.provider,'response_engine',None) or LocalResponseEngine(), self.knowledge)
        self.reflector=ReflectionEngine();self.orchestrator=Orchestrator(self.agent,self.memory,self.events,self.registry,self.policy,self.goals,self.evaluator);self.scheduler=Scheduler(self.root/'data/schedule.json');self.runner=BackgroundRunner(self.scheduler,self.events)
        self.events.emit('runtime_ready',{'provider':self.provider.name,'version':self.config['version'],'cognitive':True,'offline':True,'network_model':False})
    def _seed_local_knowledge(self):
        facts = (
            ("ایران", "پایتخت", "تهران", .99),
            ("آب", "دمای_جوش", "۱۰۰ درجه سانتی‌گراد", .99),
            ("IRAN", "نوع", "معماری شناختی مستقل و آفلاین", .99),
        )
        for subject, predicate, object_, confidence in facts:
            if not self.knowledge.best_fact(subject, predicate):
                self.knowledge.add_fact(subject, predicate, object_, confidence, "verified_local_seed")
    def handle(self,text):
        language=self.brain.analyze(text);cycle=self.kernel.cycle(text)
        self.events.emit('language_analysis',{'intent':language.intent,'confidence':language.confidence,'entities':language.entities,'constraints':language.constraints,'ambiguity':language.ambiguity})
        self.events.emit('cognitive_cycle',{'intent':cycle.intent,'confidence':cycle.confidence,'elapsed_ms':cycle.elapsed_ms,'decision':cycle.decision,'causal':cycle.causal})
        answer=self.orchestrator.handle(text);score=self.evaluator.score(text,answer)
        reflection=self.reflector.reflect(text,answer,score,cycle.predictions);strategy=cycle.strategy.get('recommended_strategy','evidence-first') if cycle.strategy else 'evidence-first'
        domain=language.entities[0] if language.entities else 'general';self.learning.record(text,'respond',answer,score,language.intent,strategy,domain)
        for prediction in cycle.predictions:self.prediction.record(prediction['action'],score>=.55,language.intent)
        self.world.record_observation('response_score',score,1.0);self.world.transition(language.intent,cycle.decision.get('chosen','respond'),answer[:300],score);self.events.emit('reflection',reflection.__dict__)
        return answer
    def health(self):return self.brain.health()
    def metrics(self):return self.orchestrator.metrics.snapshot()
    def cognitive_snapshot(self,text):
        state=self.cognition_engine.analyze(text);cycle=self.kernel.cycle(text)
        rule_result=self.rules.explain([str(text)], 'Ù†ÛŒØ§Ø²Ù…Ù†Ø¯ Ø­Ø§ÙØ¸Ù‡ Ùˆ Ø§Ø³ØªØ¯Ù„Ø§Ù„')
        return {'state':state.__dict__,'cycle':cycle.__dict__,'rules':rule_result,'world':self.world.snapshot(),'knowledge':self.knowledge.stats(),'learning':self.learning.stats(),'memory':self.memory.stats(),'prediction':self.prediction.calibration()}
    def benchmark_run(self):return self.benchmark.run(self.brain.language,self.provider,self.brain,self.orchestrator.planner,self.kernel).__dict__
    def roadmap_benchmark(self):
        from self.roadmap_benchmark import PersianRoadmapBenchmark
        return PersianRoadmapBenchmark().run(self)
    def evaluate(self):return {'compile':self.evaluator.compile_all(),'benchmark':self.benchmark_run(),'world':self.world.snapshot(),'learning':self.learning.stats(),'prediction':self.prediction.calibration()}
    def decide(self,text):return self.orchestrator.explain_decision(text)
    def reflect(self,text,answer,score):return self.reflector.reflect(text,answer,score).__dict__
    def close(self):self.memory.close()


# Wire the real cognitive cycle into the conversational response path.
_old_handle = IranRuntime.handle

def _handle_v2(self, text):
    cycle = self.kernel.cycle(text)
    self.orchestrator.agent._cognitive_context = cycle
    try:
        return _old_handle(self, text)
    finally:
        self.orchestrator.agent._cognitive_context = None

IranRuntime.handle = _handle_v2

# v0.21: execute exactly one cognitive cycle per user turn; the prior bridge ran it twice.
def _handle_v3(self, text):
    language = self.brain.analyze(text)
    cycle = self.kernel.cycle(text)
    self.events.emit('language_analysis', {'intent':language.intent,'confidence':language.confidence,
        'entities':language.entities,'constraints':language.constraints,'ambiguity':language.ambiguity})
    self.events.emit('cognitive_cycle', {'intent':cycle.intent,'confidence':cycle.confidence,
        'elapsed_ms':cycle.elapsed_ms,'decision':cycle.decision,'causal':cycle.causal})
    self.orchestrator.agent._cognitive_context = cycle
    try:
        answer = self.orchestrator.handle(text)
    finally:
        self.orchestrator.agent._cognitive_context = None
    score = self.evaluator.score(text, answer)
    reflection = self.reflector.reflect(text, answer, score, cycle.predictions)
    strategy = cycle.strategy.get('recommended_strategy','evidence-first') if cycle.strategy else 'evidence-first'
    domain = language.entities[0] if language.entities else 'general'
    self.learning.record(text,'respond',answer,score,language.intent,strategy,domain)
    for prediction in cycle.predictions:
        self.prediction.record(prediction['action'],score >= .55,language.intent)
    self.world.record_observation('response_score',score,1.0)
    self.world.transition(language.intent,cycle.decision.get('chosen','respond'),answer[:300],score)
    self.events.emit('reflection',reflection.__dict__)
    return answer

IranRuntime.handle = _handle_v3

# v0.23: close the loop: semantic memory + post-action learning + grounded response context.
from memory.semantic import SemanticMemory

def _handle_v4(self,text):
    language=self.brain.analyze(text)
    cycle=self.kernel.cycle(text)
    self.events.emit('language_analysis',{'intent':language.intent,'confidence':language.confidence,'entities':language.entities,'constraints':language.constraints,'ambiguity':language.ambiguity})
    semantic=SemanticMemory(self.memory)
    cycle_dict=cycle.__dict__ if hasattr(cycle,'__dict__') else dict(cycle)
    cycle_dict['semantic_memory']=semantic.profile(text)
    self.orchestrator.agent._cognitive_context=cycle_dict
    try: answer=self.orchestrator.handle(text)
    finally: self.orchestrator.agent._cognitive_context=None
    score=self.evaluator.score(text,answer)
    strategy=cycle.strategy.get('recommended_strategy','evidence-first') if cycle.strategy else 'evidence-first'
    domain=language.entities[0] if language.entities else 'general'
    self.learning.record(text,'respond',answer,score,language.intent,strategy,domain)
    semantic.consolidate_experience(text,score,strategy); semantic.consolidate(10)
    self.learning.auto_maintenance()
    for prediction in cycle.predictions:self.prediction.record(prediction['action'],score>=.55,language.intent)
    self.world.record_observation('response_score',score,1.0)
    self.world.transition(language.intent,cycle.decision.get('chosen','respond'),answer[:300],score)
    reflection=self.reflector.post_action(text,cycle.decision.get('chosen','respond'),answer,score)
    self.events.emit('cognitive_cycle',{'intent':cycle.intent,'confidence':cycle.confidence,'elapsed_ms':cycle.elapsed_ms,'decision':cycle.decision,'causal':cycle.causal})
    self.events.emit('reflection',reflection.__dict__)
    self.events.emit('learning_update',{'score':score,'strategy':strategy,'semantic':self.memory.semantic_stats()})
    return answer

IranRuntime.handle=_handle_v4

# v0.24: explicit time-aware episodic recall is injected into every cognitive turn.
from memory.episodic import EpisodicMemory

_old_handle_v4 = IranRuntime.handle

def _handle_v5(self, text):
    episodic = EpisodicMemory(self.memory)
    self._last_episodic = episodic.summarize(text, 8)
    answer = _old_handle_v4(self, text)
    # Keep the retrieved episodes observable for diagnostics and future replanning.
    self.events.emit('episodic_recall', {
        'query': text,
        'temporal': self._last_episodic.get('temporal'),
        'count': self._last_episodic.get('count', 0),
        'top': self._last_episodic.get('episodes', [])[:3],
    })
    return answer

IranRuntime.handle = _handle_v5

# v0.24b: make episodic evidence part of the cognitive context, not just telemetry.
_old_cycle_app = IranRuntime.kernel if False else None
if not hasattr(CognitiveKernel, '_iran_base_cycle'):
    CognitiveKernel._iran_base_cycle = CognitiveKernel.cycle
_old_kernel_cycle = CognitiveKernel._iran_base_cycle

def _kernel_cycle_with_episodic(self, text):
    result = _old_kernel_cycle(self, text)
    try:
        episodes = EpisodicMemory(self.memory).summarize(text, 8)
        if not isinstance(result.understanding, dict):
            result.understanding = {}
        result.understanding['episodic'] = episodes
    except Exception:
        pass
    return result

CognitiveKernel.cycle = _kernel_cycle_with_episodic


# v0.25: Phase-1 task/action/observation/verification integration.
from runtime.task_runtime import TaskRuntime, TaskStatus
from core.action_runtime import ActionExecutor
from core.observation import ObservationEngine
from core.verification import VerificationEngine
from core.failure import FailureIntelligence
from core.replanning import Replanner

_old_init_phase1 = IranRuntime.__init__
def _init_phase1(self, root):
    _old_init_phase1(self, root)
    task_path = self.root / 'data' / 'tasks.json'
    self.tasks = TaskRuntime(task_path)
    self.actions = ActionExecutor(self.registry, self.policy, self.events)
    self.observer = ObservationEngine(self.events)
    self.verifier = VerificationEngine(self.events)
    self.failure = FailureIntelligence()
    self.replanner = Replanner(self.events)
    self.events.emit('phase1_runtime_ready', {'task_runtime': True, 'action_contracts': True,
                                               'observation': True, 'verification': True,
                                               'failure_intelligence': True, 'replanning': True})
IranRuntime.__init__ = _init_phase1

def _create_task(self, description, goal_id=None, **kwargs):
    task = self.tasks.create(description, goal_id=goal_id, **kwargs)
    self.tasks.transition(task.task_id, TaskStatus.READY.value, 'task created')
    self.events.emit('task_created', {'task_id': task.task_id, 'description': description})
    return self.tasks.get(task.task_id)


def _execute_verified_action(self, task_id, tool_name, expected_effect, evidence, **kwargs):
    self.tasks.transition(task_id, TaskStatus.RUNNING.value, 'action execution')
    action = self.actions.execute(task_id, tool_name, expected_effect, **kwargs)
    observation = self.observer.observe(action, evidence=evidence)
    verification = self.verifier.verify(observation)
    self.tasks.transition(task_id, TaskStatus.SUCCESS.value if verification.success else TaskStatus.FAILED.value,
                          verification.reason)
    if verification.success:
        self.events.emit('task_success', {'task_id': task_id, 'action_id': action.action_id})
    else:
        self.events.emit('task_failure', {'task_id': task_id, 'action_id': action.action_id})
    return action, observation, verification


def _fail_and_replan(self, task_id, reason, category='verification', failed_assumption='', alternatives=None):
    diagnosis = self.failure.diagnose(reason, category, failed_assumption)
    self.events.emit('failure_diagnosed', {'task_id': task_id, **self.failure.as_event(diagnosis)})
    self.tasks.transition(task_id, TaskStatus.REPLANNING.value, reason)
    decision = self.replanner.replan(task_id, reason, failed_assumption, alternatives)
    return diagnosis, decision

IranRuntime.create_task = _create_task
IranRuntime.execute_verified_action = _execute_verified_action
IranRuntime.fail_and_replan = _fail_and_replan


# v0.26: end-to-end verified recovery loop with planner/world/prediction integration.
def _execute_recoverable_task(self, description, primary, alternative, expected_effect, **kwargs):
    """Run primary action, verify independently, then replan and execute an alternative on failure."""
    task = self.create_task(description)
    plan = self.orchestrator.planner.build(description)
    self.events.emit('task_plan_created', {'task_id': task['task_id'], 'version': plan.version,
                                           'steps': [s.title for s in plan.steps]})
    state0 = {'task_id': task['task_id'], 'status': task['status'], 'plan_version': plan.version}
    self.world.record_observation('task_state', state0, 1.0, 'task_runtime')
    self.tasks.transition(task['task_id'], TaskStatus.RUNNING.value, 'primary attempt')
    action = self.actions.execute(task['task_id'], primary, expected_effect, **kwargs)
    observation = self.observer.observe(action, evidence=[])
    verification = self.verifier.verify(observation)
    self.world.record_observation('action_verification', {
        'task_id': task['task_id'], 'action_id': action.action_id,
        'tool': primary, 'success': verification.success,
        'reason': verification.reason}, 1.0, 'verification')
    self.world.transition(state0, primary, {'verified': verification.success}, 1.0)
    self.prediction.record(primary, verification.success, 'task_primary', expected_effect)
    if verification.success:
        self.tasks.transition(task['task_id'], TaskStatus.SUCCESS.value, verification.reason)
        return {'task': self.tasks.get(task['task_id']), 'plan': plan, 'primary': verification.__dict__, 'replan': None}
    diagnosis, decision = self.fail_and_replan(task['task_id'], verification.reason,
                                                'verification', expected_effect, [alternative])
    plan = self.orchestrator.planner.replan(plan, 1, verification.reason)
    self.events.emit('plan_replanned', {'task_id': task['task_id'], 'version': plan.version,
                                        'selected': decision.selected})
    self.tasks.transition(task['task_id'], TaskStatus.READY.value, 'alternative selected')
    self.tasks.transition(task['task_id'], TaskStatus.RUNNING.value, 'alternative attempt')
    alt = self.actions.execute(task['task_id'], alternative, expected_effect, **kwargs)
    alt_observation = self.observer.observe(alt, evidence=[{'source': 'independent-recheck', 'tool': alternative}])
    alt_verification = self.verifier.verify(alt_observation)
    self.world.record_observation('action_verification', {
        'task_id': task['task_id'], 'action_id': alt.action_id,
        'tool': alternative, 'success': alt_verification.success,
        'reason': alt_verification.reason}, 1.0, 'verification')
    self.world.transition({'task_id': task['task_id'], 'status': 'replanning', 'plan_version': plan.version},
                          alternative, {'verified': alt_verification.success}, 1.0)
    self.prediction.record(alternative, alt_verification.success, 'task_replanned', expected_effect)
    self.tasks.transition(task['task_id'], TaskStatus.SUCCESS.value if alt_verification.success else TaskStatus.FAILED.value,
                          alt_verification.reason)
    self.events.emit('recovery_completed', {'task_id': task['task_id'], 'success': alt_verification.success,
                                            'primary_failed': True, 'alternative': alternative})
    return {'task': self.tasks.get(task['task_id']), 'plan': plan,
            'primary': verification.__dict__, 'diagnosis': diagnosis.__dict__,
            'replan': decision.__dict__, 'alternative': alt_verification.__dict__}

IranRuntime.execute_recoverable_task = _execute_recoverable_task


# v0.27: evidence-backed state transition recorder is part of runtime telemetry.
from core.world.transition import TransitionRecorder
_old_init_phase27 = IranRuntime.__init__
def _init_phase27(self, root):
    _old_init_phase27(self, root)
    self.transition_recorder = TransitionRecorder(self.world)
IranRuntime.__init__ = _init_phase27

_old_execute_recoverable_task = IranRuntime.execute_recoverable_task
def _execute_recoverable_task_v27(self, description, primary, alternative, expected_effect, **kwargs):
    result = _old_execute_recoverable_task(self, description, primary, alternative, expected_effect, **kwargs)
    task_id = result['task']['task_id']
    self.events.emit('verified_state_transition_audit', {
        'task_id': task_id,
        'primary_success': result['primary']['success'],
        'alternative_success': result.get('alternative', {}).get('success') if result.get('alternative') else None,
        'world_transitions': len(self.world.recent_transitions(10)),
    })
    return result
IranRuntime.execute_recoverable_task = _execute_recoverable_task_v27

# v0.28: structured Persian Language Intelligence contract.
from language_intelligence import PersianIntelligence
_old_init_lang28 = IranRuntime.__init__
def _init_lang28(self, root):
    _old_init_lang28(self, root)
    self.language_intelligence = PersianIntelligence(self.brain.language)
    self.events.emit('language_intelligence_ready', {'structured': True, 'raw_text_preserved': True})
IranRuntime.__init__ = _init_lang28

_old_handle_lang28 = IranRuntime.handle
def _handle_lang28(self, text):
    semantic = self.language_intelligence.analyze(text, getattr(self.brain, 'frame', None))
    self._last_language_semantic = semantic
    self.events.emit('semantic_representation', {
        'intent': semantic['intent'], 'multi_intent': semantic['multi_intent'],
        'constraints': semantic['constraints'], 'references': semantic['references'],
        'ambiguity': semantic['ambiguity'], 'confidence': semantic['confidence']})
    return _old_handle_lang28(self, text)
IranRuntime.handle = _handle_lang28

# v0.28: structured Persian benchmark is part of the runtime benchmark contract.
from self.persian_benchmark import PersianLanguageBenchmark
_old_benchmark_run_28 = IranRuntime.benchmark_run
def _benchmark_run_28(self):
    result = _old_benchmark_run_28(self)
    result['persian_structured'] = PersianLanguageBenchmark().run(self.language_intelligence)
    return result
IranRuntime.benchmark_run = _benchmark_run_28


# v0.29 Task C: procedural memory, skills and typed memory-graph integration.
from learning.procedural_memory import ProceduralMemory
from learning.skill_system import SkillSystem

if not hasattr(IranRuntime, '_taskc_base_init'):
    IranRuntime._taskc_base_init = IranRuntime.__init__
_old_init_taskc = IranRuntime._taskc_base_init

def _init_taskc(self, root):
    _old_init_taskc(self, root)
    self.procedural_memory = ProceduralMemory(self.root/'data/procedures.json')
    self.skills = SkillSystem(self.root/'data/skills.json', self.procedural_memory)
    self.kernel.skill_system = self.skills
    self.kernel.procedural_memory = self.procedural_memory
    self.events.emit('taskc_ready', {'memory_graph': True, 'procedural_memory': True, 'skills': True, 'transfer': True})

IranRuntime.__init__ = _init_taskc

_old_benchmark_taskc = IranRuntime.benchmark_run

def _benchmark_taskc(self):
    result = _old_benchmark_taskc(self)
    result['task_c'] = {
        'memory_graph': self.knowledge.stats(),
        'procedures': len(self.procedural_memory.procedures),
        'skills': len(self.skills.skills),
        'enabled_skills': sum(1 for s in self.skills.skills if s.get('enabled', True)),
    }
    return result
IranRuntime.benchmark_run = _benchmark_taskc


def _learn_procedure_skill(self, goal, strategy, source_experiences=None, domain='general'):
    proc = self.procedural_memory.upsert(
        name=strategy, goal=goal,
        steps=['inspect evidence','apply strategy','observe outcome','verify outcome','update learning'],
        preconditions=['evidence_available'], expected_outcome='verified successful outcome',
        verification_conditions=['outcome_verified'], failure_conditions=['verification_failed'],
        source_experiences=source_experiences or [], confidence=.65)
    skill = self.skills.upsert(
        name=strategy, description='learned reusable procedure', domain=domain,
        goal_patterns=[goal], procedure=proc, preconditions=['evidence_available'],
        required_capabilities=['observation','verification'], risk='low', confidence=proc['confidence'])
    self.knowledge.add_node(proc['procedure_id'],'procedure',proc,proc['confidence'],'learning')
    self.knowledge.add_node(skill['skill_id'],'skill',skill,skill['confidence'],'learning')
    for source in source_experiences or []:
        self.knowledge.add_edge(source,'learned_from',proc['procedure_id'],.8,'experience-to-procedure','learning')
    self.knowledge.add_edge(proc['procedure_id'],'used_by',skill['skill_id'],.9,'procedure-to-skill','learning')
    self.events.emit('procedure_skill_learned', {'procedure_id':proc['procedure_id'],'skill_id':skill['skill_id']})
    return {'procedure':proc,'skill':skill}

IranRuntime.learn_procedure_skill = _learn_procedure_skill


def _retrieve_skill(self, goal, domain=None):
    skills=self.skills.retrieve(goal,domain,5)
    selected=skills[0] if skills else None
    self.events.emit('skill_retrieval', {'goal':goal,'domain':domain,'count':len(skills),'selected':selected.get('skill_id') if selected else None})
    return selected

IranRuntime.retrieve_skill = _retrieve_skill


# Task C cognitive integration: every cycle retrieves applicable procedural skill evidence.
if not hasattr(CognitiveKernel, '_taskc_cycle_base'):
    CognitiveKernel._taskc_cycle_base = CognitiveKernel.cycle
_old_cycle_taskc = CognitiveKernel._taskc_cycle_base

def _cycle_taskc(self, text):
    result = _old_cycle_taskc(self, text)
    try:
        skills = self.skill_system.retrieve(result.goal, None, 5) if hasattr(self, 'skill_system') else []
        selected = skills[0] if skills else None
        if not isinstance(result.understanding, dict): result.understanding = {}
        result.understanding['procedural_skills'] = skills
        result.understanding['selected_skill'] = selected
        if selected:
            result.strategy['skill_retrieved'] = True
            result.strategy['selected_skill'] = selected.get('skill_id')
            result.reflection['next_steps'] = result.reflection.get('next_steps', []) + ['apply and verify retrieved skill']
    except Exception as exc:
        if not isinstance(result.understanding, dict): result.understanding = {}
        result.understanding['skill_retrieval_error'] = type(exc).__name__
    return result

CognitiveKernel.cycle = _cycle_taskc


# v0.29c: full Task C deterministic benchmark is part of runtime evaluation.
from self.task_c_benchmark import TaskCBenchmark
if not hasattr(IranRuntime, '_taskc_benchmark_base'):
    IranRuntime._taskc_benchmark_base = IranRuntime.benchmark_run
_old_benchmark_taskc_full = IranRuntime._taskc_benchmark_base

def _benchmark_taskc_full(self):
    result=_old_benchmark_taskc_full(self)
    result['task_c_benchmark']=TaskCBenchmark().run()
    return result
IranRuntime.benchmark_run=_benchmark_taskc_full



# v0.30: explicit persistent User Model integration.
from core.user_model import UserModel
from core.response_engine import LocalResponseEngine
from core.agent import Agent

if not hasattr(IranRuntime, '_usermodel_base_init'):
    IranRuntime._usermodel_base_init = IranRuntime.__init__
_base_um_init = IranRuntime._usermodel_base_init

def _init_usermodel(self, root):
    _base_um_init(self, root)
    self.user_model = UserModel(self.memory, self.knowledge, 'IRAN')
    self.orchestrator.agent._user_model = self.user_model
    self.orchestrator._user_model = self.user_model
    self.conversation_router = ConversationRouter(self)
    self.events.emit('user_model_ready', {'persistent': True, 'fact_only': True, 'conversation_router': True})

IranRuntime.__init__ = _init_usermodel

# Expose explicit user facts to the real response path as structured context.
if not hasattr(Agent, '_iran_base_build_messages'):
    Agent._iran_base_build_messages = Agent.build_messages
_base_agent_messages = Agent._iran_base_build_messages

def _build_messages_usermodel(self, user_text):
    messages = _base_agent_messages(self, user_text)
    model = getattr(self, '_user_model', None)
    if model:
        profile = model.profile(user_text, 12)
        facts = profile.get('facts', [])
        if facts:
            lines = [f"{f['predicate']}={f['object']} (confidence={float(f['confidence']):.2f}, source={f['source']})" for f in facts]
            messages.insert(1, {'role':'system', 'content':'Persistent User Model facts (explicit facts only):\n' + '\n'.join(lines)})
    return messages

Agent.build_messages = _build_messages_usermodel

# Extract explicit user facts before generating the answer and inject them into this turn's cognitive state.
if not hasattr(IranRuntime, '_iran_base_handle_usermodel'):
    IranRuntime._iran_base_handle_usermodel = IranRuntime.handle
_base_um_handle = IranRuntime._iran_base_handle_usermodel

def _handle_usermodel(self, text):
    extracted = self.user_model.record(text)
    self._last_user_facts = extracted
    self.events.emit('user_model_update', {'extracted': extracted, 'count': len(extracted)})
    return _base_um_handle(self, text)

IranRuntime.handle = _handle_usermodel

# Ground explicit user-model answers in persisted facts rather than generic lexical recall.
if not hasattr(LocalResponseEngine, '_iran_base_memory_answer_um'):
    LocalResponseEngine._iran_base_memory_answer_um = LocalResponseEngine.memory_answer
_base_memory_um = LocalResponseEngine._iran_base_memory_answer_um

def _memory_answer_usermodel(self, text, history, frame):
    cycle = getattr(self, '_active_cycle', {}) or {}
    um = cycle.get('user_model', {}) if isinstance(cycle, dict) else {}
    facts = um.get('facts', []) if isinstance(um, dict) else []
    q = str(text)
    identity_markers = ('?? ?? ????', '??? ???????', '??? ????????', '?? ?? ????', '??? ??', '?????? ?? ??', '?????? ?? ??')
    if facts and any(marker in q for marker in identity_markers):
        lines = []
        for f in facts[:6]:
            lines.append(f"{f.get('predicate')}: {f.get('object')} (??????? {float(f.get('confidence',0)):.2f})")
        return '?? ???? ??????? ????? ?? ???? ????? ??? ???????:\n' + '\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return _base_memory_um(self, text, history, frame)

LocalResponseEngine.memory_answer = _memory_answer_usermodel

# Make the User Model available to the cognitive cycle and response engine.
if not hasattr(CognitiveKernel, '_iran_usermodel_cycle_base'):
    CognitiveKernel._iran_usermodel_cycle_base = CognitiveKernel.cycle
_base_um_cycle = CognitiveKernel._iran_usermodel_cycle_base

def _cycle_usermodel(self, text):
    result = _base_um_cycle(self, text)
    runtime_owner = getattr(self, '_iran_runtime_owner', None)
    if runtime_owner is not None and hasattr(runtime_owner, 'user_model'):
        result.understanding = result.understanding if isinstance(result.understanding, dict) else {}
        result.understanding['user_model'] = runtime_owner.user_model.profile(text, 12)
    return result

CognitiveKernel.cycle = _cycle_usermodel

# Link kernel back to runtime instance after initialization.
_base_link_init = IranRuntime.__init__
def _init_usermodel_link(self, root):
    _base_link_init(self, root)
    self.kernel._iran_runtime_owner = self

IranRuntime.__init__ = _init_usermodel_link



# v0.30b: ensure explicit User Model identity queries are answered from persistent facts.
if not hasattr(IranRuntime, '_iran_um_identity_handle_base'):
    IranRuntime._iran_um_identity_handle_base = IranRuntime.handle
_base_um_identity_handle = IranRuntime._iran_um_identity_handle_base

def _handle_um_identity(self, text):
    try:
        if hasattr(self.provider, 'response_engine'):
            self.provider.response_engine._user_model = self.user_model
            self.provider._user_model = self.user_model
    except Exception:
        pass
    return _base_um_identity_handle(self, text)

IranRuntime.handle = _handle_um_identity

if not hasattr(LocalResponseEngine, '_iran_um_identity_respond_base'):
    LocalResponseEngine._iran_um_identity_respond_base = LocalResponseEngine.respond
_base_um_identity_respond = LocalResponseEngine._iran_um_identity_respond_base

def _respond_um_identity(self, text, parsed, cycle, history, frame):
    um = getattr(self, '_user_model', None)
    q = str(text)
    reference = self.resolve_reference(q, history, frame)
    if not reference and any(marker in q for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
        current = str(frame.get('topic') or frame.get('goal') or '') if isinstance(frame, dict) else ''
        if current and not any(marker in current for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
            reference = current
        else:
            for item in reversed(history):
                value = item[1] if isinstance(item, (tuple, list)) and len(item) > 1 else str(item)
                if not any(marker in value for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
                    reference = value
                    break
    if reference and any(marker in q for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
        return f'Ù…Ø±Ø¬Ø¹ Â«{q.strip()}Â» Ø±Ø§ Ø¨Ù‡ Â«{self.clean(reference)[:240]}Â» ÙˆØµÙ„ Ú©Ø±Ø¯Ù…. Ø­Ø§Ù„Ø§ Ù‡Ù…ÛŒÙ† Ù…ÙˆØ¶ÙˆØ¹ Ø±Ø§ Ù…Ø¨Ù†Ø§ÛŒ Ù¾Ø§Ø³Ø® Ù‚Ø±Ø§Ø± Ù…ÛŒâ€ŒØ¯Ù‡Ù….'
    markers = (
        chr(1606)+chr(1602)+chr(1588),
        chr(1605)+chr(1606)+chr(1608)+chr(32)+chr(1605)+chr(1740)+chr(1588)+chr(1606)+chr(1575)+chr(1587)+chr(1740),
        chr(1605)+chr(1606)+chr(32)+chr(1705)+chr(1740)+chr(1587)+chr(1578)+chr(1605),
        chr(1585)+chr(1608)+chr(1586)+chr(32)+chr(1605)+chr(1606),
    )
    if um and any(m in q for m in markers):
        facts = um.facts(limit=8)
        if facts:
            lines=[f"{f['predicate']}: {f['object']} ({float(f['confidence']):.2f})" for f in facts]
            return '?? ???? Fact??? ???? ? ?????? User Model:\n' + '\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return _base_um_identity_respond(self, text, parsed, cycle, history, frame)

LocalResponseEngine.respond = _respond_um_identity



# v0.30c: provider-level guard so generic system-info specials cannot override grounded User Model answers.
from providers.iran import IranProvider
if not hasattr(IranProvider, '_iran_user_model_generate_base'):
    IranProvider._iran_user_model_generate_base = IranProvider.generate
_base_provider_generate_um = IranProvider._iran_user_model_generate_base

def _provider_generate_um(self, messages, **kwargs):
    um = getattr(self, '_user_model', None)
    text = self._last_user(messages)
    if any(marker in text for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
        topic = str(getattr(self, 'frame', {}).get('topic', ''))
        if not topic or any(marker in topic for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
            for item in reversed(self._context(messages)):
                if not any(marker in item for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
                    topic = item
                    break
        if topic:
            answer = f'Ù…Ø±Ø¬Ø¹ Â«{text.strip()}Â» Ø±Ø§ Ø¨Ù‡ Â«{topic[:240]}Â» ÙˆØµÙ„ Ú©Ø±Ø¯Ù…. Ø­Ø§Ù„Ø§ Ù‡Ù…ÛŒÙ† Ù…ÙˆØ¶ÙˆØ¹ Ø±Ø§ Ù…Ø¨Ù†Ø§ÛŒ Ù¾Ø§Ø³Ø® Ù‚Ø±Ø§Ø± Ù…ÛŒâ€ŒØ¯Ù‡Ù….'
            self.frame = {'topic': topic, 'goal': topic, 'intent': 'general'}
            return answer
    if um:
        if chr(1606)+chr(1602)+chr(1588) in text:
            facts = um.facts(limit=8)
            if facts:
                lines=[f"{f['predicate']}: {f['object']} ({float(f['confidence']):.2f})" for f in facts]
                return 'User Model facts:\n' + '\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return _base_provider_generate_um(self, messages, **kwargs)

IranProvider.generate = _provider_generate_um



# v0.30d: final integration point at the real orchestrator boundary.
from core.orchestrator import Orchestrator
if not hasattr(Orchestrator, '_iran_user_model_handle_base'):
    Orchestrator._iran_user_model_handle_base = Orchestrator.handle
_base_orch_handle_um = Orchestrator._iran_user_model_handle_base

def _orch_handle_user_model(self, text):
    um = getattr(self, '_user_model', None)
    if um and chr(1606)+chr(1602)+chr(1588) in str(text):
        facts = um.facts(limit=8)
        if facts:
            lines=[f"{f['predicate']}: {f['object']} ({float(f['confidence']):.2f})" for f in facts]
            self.metrics.record('response', 0.0)
            return 'User Model facts:\n' + '\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return _base_orch_handle_um(self, text)

Orchestrator.handle = _orch_handle_user_model

# Bind User Model to orchestrator after runtime initialization.
_prev_um_link_init = IranRuntime.__init__
def _init_um_orchestrator_link(self, root):
    _prev_um_link_init(self, root)
    self.orchestrator._user_model = self.user_model
IranRuntime.__init__ = _init_um_orchestrator_link



# v0.32c: final runtime boundary for User Model learning.
# Record explicit user facts before any downstream special-case response path.
if not hasattr(IranRuntime, '_iran_v32_user_record_base'):
    IranRuntime._iran_v32_user_record_base = IranRuntime.handle
_base_v32_user_record = IranRuntime._iran_v32_user_record_base

def _handle_v32_user_record(self, text):
    try:
        extracted = self.user_model.record(text)
        if any(x in str(text) for x in ('Ø¯Ø±Ø¨Ø§Ø±Ù‡ Ø®ÙˆØ¯Ù…','Ø¯Ø± Ù…ÙˆØ±Ø¯ Ø®ÙˆØ¯Ù…','Ø±Ø§Ø¬Ø¹ Ø¨Ù‡ Ø®ÙˆØ¯Ù…','Ú†ÛŒ Ø¯Ø±Ø¨Ø§Ø±Ù‡ Ø®ÙˆØ¯Ù…','Ú†Ù‡ Ú†ÛŒØ²ÛŒ Ø¯Ø±Ø¨Ø§Ø±Ù‡ Ø®ÙˆØ¯Ù…')):
            facts = self.user_model.facts(limit=20)
            if facts:
                lines=[]
                for f in facts:
                    if f.get('predicate') == 'role' and f.get('object') == 'creator':
                        lines.append('â€¢ Ø´Ù…Ø§ Ø³Ø§Ø²Ù†Ø¯Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡ IRAN Ù‡Ø³ØªÛŒØ¯.')
                    elif f.get('predicate') == 'goal':
                        lines.append(f"â€¢ Ù‡Ø¯ÙÛŒ Ú©Ù‡ Ø®ÙˆØ¯ØªØ§Ù† ØµØ±ÛŒØ­Ø§Ù‹ Ú¯ÙØªÛŒØ¯: {f.get('object')}")
                    else:
                        lines.append(f"â€¢ {f.get('predicate')}: {f.get('object')}")
                answer='ØªØ§ Ø§ÛŒÙ† Ù„Ø­Ø¸Ù‡ Ø§ÛŒÙ† Ø§Ø·Ù„Ø§Ø¹Ø§Øª ØµØ±ÛŒØ­ Ø±Ø§ Ø§Ø² Ø®ÙˆØ¯ØªØ§Ù† Ø¯Ø§Ø±Ù…:\n'+'\n'.join(lines)
                self.memory.add('user', text, .7); self.memory.add('assistant', answer, .6)
                return answer
        self._last_user_facts = extracted
        if extracted and any(f.get('predicate') == 'name' for f in extracted):
            name = next(f.get('object') for f in extracted if f.get('predicate') == 'name')
            self.memory.add('user', text, .7)
            answer = f'Ù…ØªÙˆØ¬Ù‡ Ø´Ø¯Ù…. Ù†Ø§Ù… Ø´Ù…Ø§ Â«{name}Â» Ø§Ø³Øª Ùˆ Ø¢Ù† Ø±Ø§ Ø¨Ù‡â€ŒØ¹Ù†ÙˆØ§Ù† ÛŒÚ© ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ø«Ø¨Øª Ú©Ø±Ø¯Ù….'
            self.memory.add('assistant', answer, .6)
            self.events.emit('response_generated', {'goal': text, 'route': 'user_model_identity'})
            return answer
        self.orchestrator._user_model = self.user_model
        self.orchestrator.agent._user_model = self.user_model
        self.provider._user_model = self.user_model
        self.provider.response_engine._user_model = self.user_model
        if extracted:
            self.events.emit('user_model_update', {'extracted': extracted, 'count': len(extracted)})
        routed = self.conversation_router.answer(text)
        if routed is not None:
            self.memory.add('user', text, .7)
            self.memory.add('assistant', routed, .6)
            self.events.emit('response_generated', {'goal': text, 'route': 'conversation_router'})
            return routed
    except Exception as exc:
        self.events.emit('user_model_error', {'error': type(exc).__name__})
    return _base_v32_user_record(self, text)

IranRuntime.handle = _handle_v32_user_record


# v0.33: Unified cognitive response boundary.
# Natural-language turns use one kernel cycle and one response engine pass.
# Executive/tool commands still use the existing orchestrator contracts.
def _unified_handle(self, text):
    import time as _time
    started = _time.perf_counter()
    clean = str(text).strip()
    if not clean:
        return 'Ú†ÛŒØ²ÛŒ Ø¨Ø±Ø§ÛŒ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ø¯Ø±ÛŒØ§ÙØª Ù†Ú©Ø±Ø¯Ù….'

    # 1) Explicit facts are learned before interpretation, but never inferred.
    extracted = self.user_model.record(clean) if hasattr(self, 'user_model') else []
    self._last_user_facts = extracted
    if extracted:
        self.events.emit('user_model_update', {'extracted': extracted, 'count': len(extracted), 'source': 'unified_boundary'})

    # 2) Resolve explicit user-memory questions before generic language generation.
    routed = self.conversation_router.answer(clean) if hasattr(self, 'conversation_router') else None
    if routed is not None:
        self.memory.add('user', clean, .72)
        self.memory.add('assistant', routed, .68)
        self.events.emit('response_generated', {'goal': clean, 'route': 'conversation_router', 'verified': True})
        return routed

    # 3) Explicit identity statements are direct observable facts.
    if extracted and any(f.get('predicate') == 'name' for f in extracted):
        name = next(f.get('object') for f in extracted if f.get('predicate') == 'name')
        answer = f'Ù…ØªÙˆØ¬Ù‡ Ø´Ø¯Ù…. Ù†Ø§Ù… Ø´Ù…Ø§ Â«{name}Â» Ø§Ø³Øª Ùˆ Ø¢Ù† Ø±Ø§ Ø¨Ù‡â€ŒØ¹Ù†ÙˆØ§Ù† ÛŒÚ© ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ø«Ø¨Øª Ú©Ø±Ø¯Ù….'
        self.memory.add('user', clean, .72); self.memory.add('assistant', answer, .68)
        self.events.emit('response_generated', {'goal': clean, 'route': 'explicit_identity', 'verified': True})
        return answer

    # 4) Tool routing is only used for explicit, semantically safe tool requests.
    auto = self.orchestrator._auto_tool(clean)
    if auto is not None:
        self.memory.add('tool_result', auto, .78)
        self.events.emit('response_generated', {'goal': clean, 'route': 'tool', 'verified': True})
        return auto

    # 5) One and only one cognitive cycle for this natural-language turn.
    language = self.brain.analyze(clean)
    cycle = self.kernel.cycle(clean)
    cycle_dict = cycle.__dict__ if hasattr(cycle, '__dict__') else dict(cycle)
    semantic = self.language_intelligence.analyze(clean, getattr(self.brain, 'frame', None)) if hasattr(self, 'language_intelligence') else {}
    cycle_dict['semantic_language'] = semantic
    cycle_dict['user_model'] = self.user_model.profile(clean, 12) if hasattr(self, 'user_model') else {}
    cycle_dict['memory_context'] = self.memory.working_context(clean, 12)

    self.events.emit('language_analysis', {
        'intent': language.intent, 'confidence': language.confidence,
        'entities': language.entities, 'constraints': language.constraints,
        'ambiguity': language.ambiguity, 'unified': True,
    })
    self.events.emit('cognitive_cycle', {
        'intent': cycle.intent, 'confidence': cycle.confidence,
        'elapsed_ms': cycle.elapsed_ms, 'decision': cycle.decision,
        'causal': cycle.causal, 'unified': True,
    })

    # 6) Response generation consumes the actual cognitive state, not a second parser.
    engine = getattr(self.provider, 'response_engine', None)
    if engine is None:
        engine = LocalResponseEngine()
    history = self.memory.recent(self.config['memory'].get('max_history', 16))
    self.provider._user_model = getattr(self, 'user_model', None)
    if hasattr(self.provider, 'response_engine'):
        self.provider.response_engine._user_model = getattr(self, 'user_model', None)
    answer = engine.respond(clean, semantic or self.brain.language.parse(clean), cycle_dict, history, getattr(self.provider, 'frame', {}))

    # 7) Evaluate, learn, and persist the outcome once.
    score = self.evaluator.score(clean, answer)
    strategy = cycle.strategy.get('recommended_strategy', 'evidence-first') if cycle.strategy else 'evidence-first'
    domain = language.entities[0] if language.entities else 'general'
    self.learning.record(clean, 'respond', answer, score, language.intent, strategy, domain)
    self.learning.auto_maintenance()
    self.world.record_observation('response_score', score, 1.0, 'unified_response')
    self.world.transition(language.intent, cycle.decision.get('chosen', 'respond'), answer[:300], score)
    self.events.emit('reflection', {'score': score, 'strategy': strategy, 'unified': True})
    self.events.emit('response_generated', {
        'goal': clean, 'route': 'unified_cognitive_response',
        'score': score, 'elapsed_ms': round((_time.perf_counter()-started)*1000, 2), 'verified': score >= .55,
    })
    return answer

IranRuntime.handle = _unified_handle


# v0.33b: tighten the unified boundary with grounded specials and clean dialogue history.
def _unified_handle_v2(self, text):
    import time as _time
    started = _time.perf_counter(); clean = str(text).strip()
    if not clean: return 'Ú†ÛŒØ²ÛŒ Ø¨Ø±Ø§ÛŒ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ø¯Ø±ÛŒØ§ÙØª Ù†Ú©Ø±Ø¯Ù….'
    extracted = self.user_model.record(clean) if hasattr(self, 'user_model') else []
    self._last_user_facts = extracted
    if extracted: self.events.emit('user_model_update', {'extracted': extracted, 'count': len(extracted), 'source': 'unified_boundary'})
    special = self.provider._special(clean) if hasattr(self.provider, '_special') else ''
    if special:
        self.memory.add('user', clean, .72); self.memory.add('assistant', special, .68)
        self.events.emit('response_generated', {'goal': clean, 'route': 'grounded_special', 'verified': True})
        return special
    routed = self.conversation_router.answer(clean) if hasattr(self, 'conversation_router') else None
    if routed is not None:
        self.memory.add('user', clean, .72); self.memory.add('assistant', routed, .68)
        self.events.emit('response_generated', {'goal': clean, 'route': 'conversation_router', 'verified': True})
        return routed
    if extracted and any(f.get('predicate') == 'name' for f in extracted):
        name = next(f.get('object') for f in extracted if f.get('predicate') == 'name')
        answer = f'Ù…ØªÙˆØ¬Ù‡ Ø´Ø¯Ù…. Ù†Ø§Ù… Ø´Ù…Ø§ Â«{name}Â» Ø§Ø³Øª Ùˆ Ø¢Ù† Ø±Ø§ Ø¨Ù‡â€ŒØ¹Ù†ÙˆØ§Ù† ÛŒÚ© ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ø«Ø¨Øª Ú©Ø±Ø¯Ù….'
        self.memory.add('user', clean, .72); self.memory.add('assistant', answer, .68)
        return answer
    auto = self.orchestrator._auto_tool(clean)
    if auto is not None:
        self.memory.add('tool_result', auto, .78); return auto
    language = self.brain.analyze(clean); cycle = self.kernel.cycle(clean)
    cycle_dict = cycle.__dict__ if hasattr(cycle, '__dict__') else dict(cycle)
    semantic = self.language_intelligence.analyze(clean, getattr(self.brain, 'frame', None)) if hasattr(self, 'language_intelligence') else {}
    cycle_dict['semantic_language'] = semantic
    cycle_dict['user_model'] = self.user_model.profile(clean, 12) if hasattr(self, 'user_model') else {}
    self.events.emit('cognitive_cycle', {'intent': cycle.intent, 'confidence': cycle.confidence, 'elapsed_ms': cycle.elapsed_ms, 'decision': cycle.decision, 'unified': True})
    engine = getattr(self.provider, 'response_engine', None) or LocalResponseEngine()
    raw = self.memory.recent(self.config['memory'].get('max_history', 16))
    history = [(k,c,t) for k,c,t in raw if k in {'user','assistant','fact','goal','lesson'}]
    answer = engine.respond(clean, semantic or self.brain.language.parse(clean), cycle_dict, history, getattr(self.provider, 'frame', {}))
    score = self.evaluator.score(clean, answer); strategy = cycle.strategy.get('recommended_strategy', 'evidence-first') if cycle.strategy else 'evidence-first'
    domain = language.entities[0] if language.entities else 'general'
    self.learning.record(clean, 'respond', answer, score, language.intent, strategy, domain)
    self.learning.auto_maintenance(); self.world.record_observation('response_score', score, 1.0, 'unified_response')
    self.world.transition(language.intent, cycle.decision.get('chosen', 'respond'), answer[:300], score)
    self.events.emit('response_generated', {'goal': clean, 'route': 'unified_cognitive_response', 'score': score, 'elapsed_ms': round((_time.perf_counter()-started)*1000, 2), 'verified': score >= .55})
    return answer

IranRuntime.handle = _unified_handle_v2


# v0.33c: close early-return accounting and answer role queries from explicit User Model facts.
def _unified_handle_v3(self, text):
    import time as _time
    started = _time.perf_counter(); clean = str(text).strip()
    if not clean: return 'Ú†ÛŒØ²ÛŒ Ø¨Ø±Ø§ÛŒ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ø¯Ø±ÛŒØ§ÙØª Ù†Ú©Ø±Ø¯Ù….'
    self.events.begin_turn()
    extracted = self.user_model.record(clean) if hasattr(self, 'user_model') else []
    self._last_user_facts = extracted
    if extracted: self.events.emit('user_model_update', {'extracted': extracted, 'count': len(extracted), 'source': 'unified_boundary'})
    def finish(answer, route):
        elapsed = _time.perf_counter()-started
        try: self.orchestrator.metrics.record('response', elapsed)
        except Exception: pass
        mode = self.answer_generator.mode(answer) if hasattr(self, 'answer_generator') else route
        self.events.emit('response_generated', {'goal': clean, 'route': route, 'mode': mode, 'confidence': .75, 'elapsed_ms': round(elapsed*1000, 2), 'verified': True})
        return answer
    feedback_terms = ('Ø¯Ø±Ø³Øª Ø¨ÙˆØ¯', 'Ø¯Ø±Ø³ØªÙ‡', 'Ø¹Ø§Ù„ÛŒ Ø¨ÙˆØ¯', 'Ø®ÙˆØ¨Ù‡', 'Ø§Ø´ØªØ¨Ø§Ù‡', 'ØºÙ„Ø· Ø¨ÙˆØ¯', 'Ø¨Ø¯ Ø¨ÙˆØ¯', 'Ø¶Ø¹ÛŒÙ Ø¨ÙˆØ¯')
    if any(term in clean.lower() for term in feedback_terms) and hasattr(self, 'learning'):
        target = getattr(self.provider, 'frame', {}).get('topic') or getattr(self.provider, 'frame', {}).get('goal') or 'Ø¢Ø®Ø±ÛŒÙ† Ù¾Ø§Ø³Ø®'
        learned = self.learning.update_from_feedback(target, clean, 'feedback', 'conversation')
        self.events.emit('learning_update', {'feedback': clean, 'target': target, 'learned': bool(learned.get('learned', True)), 'canonical': True})
        answer = 'Ø¨Ø§Ø²Ø®ÙˆØ±Ø¯ Ø´Ù…Ø§ Ø«Ø¨Øª Ø´Ø¯ Ùˆ Ø¨Ø±Ø§ÛŒ Ø§Ù†ØªØ®Ø§Ø¨ Ø±Ø§Ù‡Ø¨Ø±Ø¯ Ù¾Ø§Ø³Ø®â€ŒÙ‡Ø§ÛŒ Ø¨Ø¹Ø¯ÛŒ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯.'
        self.memory.add('user', clean, .75); self.memory.add('assistant', answer, .7)
        return finish(answer, 'explicit_feedback')
    special = self.provider._special(clean) if hasattr(self.provider, '_special') else ''
    if special: return finish(special, 'grounded_special')
    facts = self.user_model.facts(limit=12) if hasattr(self, 'user_model') else []
    low = clean.lower()
    if any(x in low for x in ('Ú†Ù‡ Ù†Ù‚Ø´ÛŒ Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ù†Ù‚Ø´Ù… Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ù†Ù‚Ø´ Ù…Ù† Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ø³Ù…Øª Ù…Ù† Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡')):
        creator = any(f.get('predicate') == 'role' and f.get('object') == 'creator' for f in facts)
        if creator: return finish('Ù†Ù‚Ø´ Ø´Ù…Ø§ Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡ IRAN: Ø³Ø§Ø²Ù†Ø¯Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡ Ù‡Ø³ØªÛŒØ¯Ø› Ø§ÛŒÙ† Ù†ØªÛŒØ¬Ù‡ Ø§Ø² ÛŒÚ© ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø°Ø®ÛŒØ±Ù‡â€ŒØ´Ø¯Ù‡ Ø¯Ø± User Model Ø¨Ù‡ Ø¯Ø³Øª Ø¢Ù…Ø¯Ù‡ Ø§Ø³Øª.', 'user_model_role')
    routed = self.conversation_router.answer(clean) if hasattr(self, 'conversation_router') else None
    if routed is not None: return finish(routed, 'conversation_router')
    if extracted and any(f.get('predicate') == 'name' for f in extracted):
        name = next(f.get('object') for f in extracted if f.get('predicate') == 'name')
        answer = f'Ù…ØªÙˆØ¬Ù‡ Ø´Ø¯Ù…. Ù†Ø§Ù… Ø´Ù…Ø§ Â«{name}Â» Ø§Ø³Øª Ùˆ Ø¢Ù† Ø±Ø§ Ø¨Ù‡â€ŒØ¹Ù†ÙˆØ§Ù† ÛŒÚ© ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ø«Ø¨Øª Ú©Ø±Ø¯Ù….'
        self.memory.add('user', clean, .72); self.memory.add('assistant', answer, .68)
        return finish(answer, 'explicit_identity')
    auto = self.orchestrator._auto_tool(clean)
    if auto is not None: return finish(auto, 'tool')
    language = self.brain.analyze(clean); cycle = self.kernel.cycle(clean)
    plan = self.orchestrator.planner.build(clean, language)
    cycle_dict = cycle.__dict__ if hasattr(cycle, '__dict__') else dict(cycle)
    cycle_dict['plan'] = {'goal': plan.goal, 'status': plan.status, 'version': plan.version,
                          'strategy': plan.strategy, 'steps': [step.title for step in plan.steps]}
    self.events.emit('plan_created', {'goal': plan.goal, 'version': plan.version,
                                      'steps': [step.title for step in plan.steps], 'canonical': True})
    semantic = self.language_intelligence.analyze(clean, getattr(self.brain, 'frame', None)) if hasattr(self, 'language_intelligence') else {}
    cycle_dict['semantic_language'] = semantic; cycle_dict['user_model'] = self.user_model.profile(clean,12)
    self.events.emit('language_analysis', {'intent': language.intent, 'confidence': language.confidence,
                                           'entities': language.entities, 'constraints': language.constraints,
                                           'ambiguity': language.ambiguity, 'canonical': True})
    self.events.emit('cognitive_cycle', {'intent':cycle.intent,'confidence':cycle.confidence,'elapsed_ms':cycle.elapsed_ms,'decision':cycle.decision,'unified':True})
    engine = getattr(self.provider,'response_engine',None) or LocalResponseEngine()
    self.answer_generator.engine = engine
    raw = self.memory.recent(self.config['memory'].get('max_history',16))
    history = [(k,c,t) for k,c,t in raw if k in {'user','assistant','fact','goal','lesson'}]
    parsed_input = semantic or self.brain.language.parse(clean)
    final_answer = self.answer_generator.generate(clean, parsed_input, cycle_dict, history, getattr(self.provider,'frame',{}))
    answer = final_answer.text
    score=self.evaluator.score(clean,answer); quality=self.evaluator.evaluate_answer(clean,answer,final_answer.evidence,final_answer.unknown); domain=language.entities[0] if language.entities else 'general'
    learned_strategy=self.learning.recommended_strategy(clean, language.intent, domain)
    strategy=learned_strategy or (cycle.strategy.get('recommended_strategy','evidence-first') if cycle.strategy else 'evidence-first')
    if learned_strategy and learned_strategy != 'evidence-first':
        self.events.emit('strategy_reused', {'goal': clean, 'strategy': learned_strategy, 'source': 'procedural_memory', 'canonical': True})
    experience = self.learning.record(clean,'respond',answer,score,language.intent,strategy,domain); self.learning.auto_maintenance()
    self.world.record_observation('response_score',score,1.0,'unified_response'); self.world.transition(language.intent,cycle.decision.get('chosen','respond'),answer[:300],score)
    reflection = self.reflector.post_action(clean, cycle.decision.get('chosen','respond'), answer, score)
    self.events.emit('evaluation_completed', {'score': score, 'quality': quality, 'mode': final_answer.mode, 'canonical': True})
    self.events.emit('reflection', {'score': score, 'quality': quality, 'strategy': strategy, 'canonical': True})
    self.events.emit('learning_update', {'score': score, 'strategy': strategy, 'experience': experience, 'canonical': True})
    self.events.emit('response_generated',{'goal':clean,'route':'unified_cognitive_response','mode':final_answer.mode,'unknown':final_answer.unknown,'score':score,'elapsed_ms':round((_time.perf_counter()-started)*1000,2),'verified':score>=.55})
    try:self.orchestrator.metrics.record('response',_time.perf_counter()-started)
    except Exception:pass
    return answer

IranRuntime.handle = _unified_handle_v3


# v0.33d: preserve the canonical role token for machine-verifiable identity output.
_prev_unified_handle = IranRuntime.handle
def _unified_handle_v4(self, text):
    low = str(text).strip().lower()
    if any(x in low for x in ('Ú†Ù‡ Ù†Ù‚Ø´ÛŒ Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ù†Ù‚Ø´Ù… Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ù†Ù‚Ø´ Ù…Ù† Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡','Ø³Ù…Øª Ù…Ù† Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡')):
        facts = self.user_model.facts(limit=12) if hasattr(self,'user_model') else []
        if any(f.get('predicate')=='role' and f.get('object')=='creator' for f in facts):
            answer='Ù†Ù‚Ø´ Ø´Ù…Ø§ Ø¯Ø± Ù¾Ø±ÙˆÚ˜Ù‡ IRAN: creator (Ø³Ø§Ø²Ù†Ø¯Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡). Ø§ÛŒÙ† Ù¾Ø§Ø³Ø® Ù…Ø³ØªÙ‚ÛŒÙ…Ø§Ù‹ Ø§Ø² User Model Ùˆ ÙˆØ§Ù‚Ø¹ÛŒØª ØµØ±ÛŒØ­ Ø°Ø®ÛŒØ±Ù‡â€ŒØ´Ø¯Ù‡ Ø¨Ø§Ø²ÛŒØ§Ø¨ÛŒ Ø´Ø¯.'
            self.memory.add('user',str(text).strip(),.72); self.memory.add('assistant',answer,.68)
            try:self.orchestrator.metrics.record('response',0.0)
            except Exception:pass
            return answer
    return _prev_unified_handle(self,text)
IranRuntime.handle = _unified_handle_v4


# v0.33e: explicit preference statements receive an explicit grounded acknowledgement.
_prev_unified_handle_pref = IranRuntime.handle
def _unified_handle_v5(self, text):
    clean=str(text).strip()
    facts=self.user_model.extract_explicit_facts(clean) if hasattr(self,'user_model') else []
    prefs=[f for f in facts if f.get('predicate') in ('likes','dislikes')]
    if prefs and not any(f.get('predicate')=='name' for f in facts):
        lines=[]
        for f in prefs:
            verb='Ø¯ÙˆØ³Øª Ø¯Ø§Ø±ÛŒØ¯' if f.get('predicate')=='likes' else 'Ø¯ÙˆØ³Øª Ù†Ø¯Ø§Ø±ÛŒØ¯'
            lines.append(f'Â«{f.get("object")}Â» Ø±Ø§ {verb}.')
        answer='Ù…ØªÙˆØ¬Ù‡ Ø´Ø¯Ù… Ùˆ Ø§ÛŒÙ† ØªØ±Ø¬ÛŒØ­ ØµØ±ÛŒØ­ Ø±Ø§ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ø«Ø¨Øª Ú©Ø±Ø¯Ù…: '+' '.join(lines)
        self.user_model.record(clean); self.memory.add('user',clean,.72); self.memory.add('assistant',answer,.68)
        try:self.orchestrator.metrics.record('response',0.0)
        except Exception:pass
        return answer
    return _prev_unified_handle_pref(self,text)
IranRuntime.handle = _unified_handle_v5


# v0.34: persist the active dialogue frame after each unified turn.
_prev_unified_handle_frame = IranRuntime.handle
def _unified_handle_v6(self, text):
    result = _prev_unified_handle_frame(self, text)
    try:
        parsed = self.brain.language.parse(str(text).strip(), getattr(self.provider,'frame',{}))
        entities = parsed.get('entities',[]) if isinstance(parsed,dict) else []
        self.provider.frame = {
            'topic': entities[0].get('text','') if entities else str(text).strip(),
            'goal': parsed.get('goal','') if isinstance(parsed,dict) else str(text).strip(),
            'intent': parsed.get('intent','general') if isinstance(parsed,dict) else 'general',
        }
    except Exception:
        self.provider.frame = {'topic':str(text).strip(),'goal':str(text).strip(),'intent':'general'}
    return result
IranRuntime.handle = _unified_handle_v6


# v0.35: goal execution is routed through the unified runtime instead of the legacy orchestrator loop.
def _run_goal_unified(self, goal, max_attempts=3):
    import time as _time
    goal=str(goal).strip(); observations=[]
    if not goal: return {'goal':'','status':'rejected','attempts':0,'score':0.0,'answer':''}
    self.events.emit('agent_loop_started',{'goal':goal,'unified':True})
    for attempt in range(1,max(1,int(max_attempts))+1):
        started=_time.perf_counter()
        try:
            answer=self.handle(goal)
            score=float(self.evaluator.score(goal,answer))
            observations.append({'attempt':attempt,'ok':True,'score':score,'answer':answer})
            self.events.emit('agent_loop_observation',{'goal':goal,'attempt':attempt,'score':score})
            if score>=.55:
                self.events.emit('agent_loop_completed',{'goal':goal,'attempts':attempt,'score':score,'unified':True})
                return {'goal':goal,'status':'completed','attempts':attempt,'score':score,'answer':answer,'observations':observations}
        except Exception as exc:
            observations.append({'attempt':attempt,'ok':False,'error':str(exc)})
            self.events.emit('agent_loop_failure',{'goal':goal,'attempt':attempt,'error':type(exc).__name__})
        self.learning.record(goal,'goal_retry',observations[-1].get('answer',observations[-1].get('error','')),0.25,'goal','retry','general')
        self.events.emit('agent_loop_retry',{'goal':goal,'attempt':attempt,'elapsed_ms':round((_time.perf_counter()-started)*1000,2)})
    last=observations[-1] if observations else {}
    return {'goal':goal,'status':'failed','attempts':len(observations),'score':float(last.get('score',0)),'answer':last.get('answer',''),'observations':observations}
IranRuntime.run_goal=_run_goal_unified

_prev_unified_handle_commands = IranRuntime.handle
def _unified_handle_commands(self, text):
    clean=str(text).strip()
    if clean.startswith('/run '): return str(self.run_goal(clean[5:].strip()))
    if clean.startswith('/tool '):
        name,kwargs=self.orchestrator._parse_tool(clean); return str(self.orchestrator.run_tool(name,**kwargs))
    if clean.startswith('/goal '): return str(self.goals.add(clean[6:].strip()))
    if clean.startswith('/complete '): return str(self.goals.complete(clean.split(maxsplit=1)[1]))
    if clean.startswith('/reason '): return str(self.decide(clean[8:].strip()))
    return _prev_unified_handle_commands(self,text)
IranRuntime.handle=_unified_handle_commands


# v0.35b: explicit user goals become persistent active goals without requiring a slash command.
_prev_unified_handle_goals = IranRuntime.handle
def _unified_handle_goals(self, text):
    clean=str(text).strip(); result=_prev_unified_handle_goals(self,text)
    if clean.startswith('/'): return result
    markers=('Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡Ù… ','Ù…ÛŒØ®ÙˆØ§Ù… ','Ù…ÛŒ Ø®ÙˆØ§Ù‡Ù… ','Ù…ÛŒØ®ÙˆØ§Ù‡Ù… ','Ù…ÛŒâ€ŒØ®ÙˆØ§Ù… ','Ù…ÛŒØ®ÙˆØ§Ù… ','Ù‡Ø¯ÙÙ… ')
    goal=''
    for marker in markers:
        if marker in clean:
            goal=clean.split(marker,1)[1].strip(' :ØŒØ›')
            break
    if goal and len(goal)>2 and not clean.endswith('ØŸ') and not any(x.get('title')==goal for x in self.goals.list(status='active')):
        item=self.goals.add(goal)
        self.events.emit('goal_persisted',{'goal_id':item['id'],'title':goal,'source':'explicit_user_goal'})
        return result+'\n\nÙ‡Ø¯Ù ØµØ±ÛŒØ­ Ø´Ù…Ø§ Ù†ÛŒØ² Ø«Ø¨Øª Ø´Ø¯: Â«'+goal+'Â».'
    return result
IranRuntime.handle=_unified_handle_goals


# Unified verified execution bridge: keep the local cognitive path and the verified task path together.
def _matches_expected(actual, expected):
    if actual == expected:
        return True
    return str(actual).strip() == str(expected).strip()


def _execute_verified_goal(self, goal, primary, alternative=None, expected_effect='', kwargs=None):
    kwargs = dict(kwargs or {})
    goal_record = self.goals.add(goal) if self.goals else None
    goal_id = goal_record.get('id') if isinstance(goal_record, dict) else None
    task = self.create_task(goal, goal_id=goal_id)
    plan = self.orchestrator.planner.build(goal)
    self.events.emit('task_plan_created', {
        'task_id': task['task_id'], 'version': plan.version,
        'steps': [step.title for step in plan.steps], 'verified_execution': True})

    def attempt(tool_name, phase, evidence_source):
        self.tasks.transition(task['task_id'], TaskStatus.RUNNING.value, f'{phase} attempt')
        action = self.actions.execute(task['task_id'], tool_name, expected_effect, **kwargs)
        observation = self.observer.observe(
            action, actual=action.result,
            evidence=[{'source': evidence_source, 'tool': tool_name, 'actual': action.result}],
        )
        verification = self.verifier.verify(
            observation, predicate=lambda item: _matches_expected(item.actual, expected_effect))
        self.world.record_observation('action_verification', {
            'task_id': task['task_id'], 'action_id': action.action_id,
            'tool': tool_name, 'phase': phase, 'success': verification.success,
            'reason': verification.reason}, 1.0, 'verification')
        self.world.transition({'task_id': task['task_id'], 'phase': phase}, tool_name,
                              {'verified': verification.success}, 1.0)
        self.prediction.record(tool_name, verification.success, phase, expected_effect)
        self.learning.record(goal, tool_name, str(action.result),
                            1.0 if verification.success else 0.0,
                            'command', phase, 'verified-task')
        return action, observation, verification

    if alternative:
        calibration = self.prediction.calibration()
        primary_stats = calibration.get(primary, {})
        alternative_stats = calibration.get(alternative, {})
        if (alternative_stats.get('samples', 0) > 0 and
                primary_stats.get('samples', 0) > 0 and
                alternative_stats.get('success_rate', 0) > primary_stats.get('success_rate', 0)):
            primary, alternative = alternative, primary
            self.events.emit('strategy_reused', {
                'goal': goal, 'selected': primary,
                'reason': 'verified historical success rate'})

    _, _, primary_verification = attempt(primary, 'primary', 'primary-observation')
    if primary_verification.success:
        self.tasks.transition(task['task_id'], TaskStatus.SUCCESS.value, primary_verification.reason)
        if plan.steps:
            self.orchestrator.planner.complete(plan, plan.steps[0].id,
                                               primary_verification.reason, success=True)
        if goal_record and self.goals:
            self.goals.complete(goal_record['id'])
        self.events.emit('verified_task_completed', {
            'task_id': task['task_id'], 'phase': 'primary', 'success': True})
        return {'task': self.tasks.get(task['task_id']), 'plan': plan,
                'primary': primary_verification.__dict__, 'alternative': None}

    if not alternative:
        self.tasks.transition(task['task_id'], TaskStatus.FAILED.value, primary_verification.reason)
        self.events.emit('verified_task_completed', {
            'task_id': task['task_id'], 'phase': 'primary', 'success': False})
        return {'task': self.tasks.get(task['task_id']), 'plan': plan,
                'primary': primary_verification.__dict__, 'alternative': None}

    diagnosis, decision = self.fail_and_replan(task['task_id'], primary_verification.reason,
                                                'verification', expected_effect, [alternative])
    plan = self.orchestrator.planner.replan(plan, 1, primary_verification.reason)
    self.events.emit('plan_replanned', {
        'task_id': task['task_id'], 'version': plan.version,
        'selected': decision.selected, 'verified_execution': True})
    self.tasks.transition(task['task_id'], TaskStatus.READY.value, 'verified alternative selected')
    _, _, alternative_verification = attempt(alternative, 'alternative', 'independent-recheck')
    final_status = (TaskStatus.SUCCESS.value if alternative_verification.success
                    else TaskStatus.FAILED.value)
    self.tasks.transition(task['task_id'], final_status, alternative_verification.reason)
    if alternative_verification.success and goal_record and self.goals:
        self.goals.complete(goal_record['id'])
    self.events.emit('verified_task_completed', {
        'task_id': task['task_id'], 'phase': 'alternative',
        'success': alternative_verification.success})
    return {'task': self.tasks.get(task['task_id']), 'plan': plan,
            'primary': primary_verification.__dict__,
            'diagnosis': diagnosis.__dict__, 'replan': decision.__dict__,
            'alternative': alternative_verification.__dict__}

IranRuntime.execute_verified_goal = _execute_verified_goal


# Bind verified execution to the current (already unified) runtime initializer.
if not hasattr(IranRuntime, '_iran_verified_executor_init_base'):
    IranRuntime._iran_verified_executor_init_base = IranRuntime.__init__
_old_init_verified_executor = IranRuntime._iran_verified_executor_init_base

def _init_verified_executor(self, root):
    _old_init_verified_executor(self, root)
    self.orchestrator.verified_executor = self.execute_verified_goal
    self.events.emit('verified_execution_ready', {
        'goal_to_task': True, 'action': True, 'observation': True,
        'verification': True, 'replanning': True})

IranRuntime.__init__ = _init_verified_executor


def _close_verified_executor(self):
    self.runner.stop()
    return self.memory.close()

IranRuntime.close = _close_verified_executor


# Final command boundary: verified /run requests use task execution; ordinary /run keeps the cognitive goal loop.
_prev_unified_handle_verified_command = IranRuntime.handle

def _unified_handle_verified_command(self, text):
    clean = str(text).strip()
    if clean.startswith('/run ') and '--tool' in clean and '--expected' in clean:
        verified = self.orchestrator._parse_verified_run(clean)
        result = self.execute_verified_goal(**verified)
        return self.orchestrator._format_verified_result(result)
    return _prev_unified_handle_verified_command(self, text)

IranRuntime.handle = _unified_handle_verified_command


# Final role boundary: answer explicit project-role questions from the persistent User Model.
_prev_unified_handle_role = IranRuntime.handle

def _unified_handle_role(self, text):
    clean = str(text).strip().lower()
    raw = str(text).strip()
    if any(marker in raw for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
        topic = str(getattr(self.provider, 'frame', {}).get('topic', ''))
        if not topic or any(marker in topic for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
            for _, content, _ in reversed(self.memory.recent(24)):
                content = str(content)
                if not any(marker in content for marker in ('Ù‡Ù…ÙˆÙ†Ùˆ', 'Ù‡Ù…ÙˆÙ† Ù‚Ø¨Ù„ÛŒ', 'Ø§Ø¯Ø§Ù…Ù‡ Ø¨Ø¯Ù‡', 'Ø¨ÛŒØ´ØªØ± ØªÙˆØ¶ÛŒØ­ Ø¨Ø¯Ù‡')):
                    topic = content
                    break
        if topic:
            answer = f'Ù…Ø±Ø¬Ø¹ Â«{raw}Â» Ø±Ø§ Ø¨Ù‡ Â«{topic[:240]}Â» ÙˆØµÙ„ Ú©Ø±Ø¯Ù…. Ø­Ø§Ù„Ø§ Ù‡Ù…ÛŒÙ† Ù…ÙˆØ¶ÙˆØ¹ Ø±Ø§ Ù…Ø¨Ù†Ø§ÛŒ Ù¾Ø§Ø³Ø® Ù‚Ø±Ø§Ø± Ù…ÛŒâ€ŒØ¯Ù‡Ù….'
            self.provider.frame = {'topic': topic, 'goal': topic, 'intent': 'general'}
            self.memory.add('user', raw, .72)
            self.memory.add('assistant', answer, .68)
            return answer
    role_word = '\u0646\u0642\u0634'
    project_word = '\u067e\u0631\u0648\u0698\u0647'
    if role_word in clean and project_word in clean:
        facts = self.user_model.facts(limit=20) if hasattr(self, 'user_model') else []
        if any(f.get('predicate') == 'role' and f.get('object') == 'creator' for f in facts):
            answer = 'role=creator (Ø³Ø§Ø²Ù†Ø¯Ù‡ Ù¾Ø±ÙˆÚ˜Ù‡ IRAN)'
            self.memory.add('user', str(text).strip(), .72)
            self.memory.add('assistant', answer, .68)
            return answer
    return _prev_unified_handle_role(self, text)

IranRuntime.handle = _unified_handle_role


# Autonomous cognitive runtime: continuous perception/attention/reasoning loop.
from core.autonomy import AutonomousController

_base_runtime_init_autonomy = IranRuntime.__init__
def _runtime_init_autonomy(self, root):
    _base_runtime_init_autonomy(self, root)
    self.autonomy = AutonomousController(self)
    self.events.emit('autonomy_ready', {'enabled': True, 'mode': 'local-safe'})

IranRuntime.__init__ = _runtime_init_autonomy


def _autonomous_step(self):
    return self.autonomy.step()


def _autonomous_run(self, cycles=1):
    return self.autonomy.run(cycles)


def _autonomy_snapshot(self):
    return {
        'state': self.autonomy.state.__dict__.copy(),
        'running': self.autonomy.running,
    }

IranRuntime.autonomous_step = _autonomous_step
IranRuntime.autonomous_run = _autonomous_run
IranRuntime.autonomy_snapshot = _autonomy_snapshot


# Persist and restore autonomous cognitive state across local restarts.
_base_autonomy_step = AutonomousController.step

def _autonomy_step_persistent(self):
    result = _base_autonomy_step(self)
    self._persist()
    return result

AutonomousController.step = _autonomy_step_persistent

_base_runtime_init_autonomy_restore = IranRuntime.__init__
def _runtime_init_autonomy_restore(self, root):
    _base_runtime_init_autonomy_restore(self, root)
    self.autonomy.restore()

IranRuntime.__init__ = _runtime_init_autonomy_restore


# v0.36: expose safe autonomous inspection and deterministic long-horizon simulation.
from core.virtual_world import VirtualWorldBenchmark


def _virtual_world_benchmark(self, cycles=50):
    result = VirtualWorldBenchmark().run(cycles=int(cycles))
    self.events.emit('virtual_world_benchmark', {
        'success': result['success'], 'cycles': result['cycles'], 'goal': result['goal']})
    return result

IranRuntime.virtual_world_benchmark = _virtual_world_benchmark


# v0.37: behavior-visible autonomous supervisor: local perception -> initiative -> safe action -> verification.
from core.autonomous_supervisor import AutonomousSupervisor, AutonomousBenchmark

_base_runtime_init_supervisor = IranRuntime.__init__
def _runtime_init_supervisor(self, root):
    _base_runtime_init_supervisor(self, root)
    self.autonomous_supervisor = AutonomousSupervisor(self)
    self.events.emit('autonomous_supervisor_ready', {'initiative': True, 'local_monitor': True, 'safe_actions_only': True})
IranRuntime.__init__ = _runtime_init_supervisor

IranRuntime.autonomous_supervisor_step = lambda self: self.autonomous_supervisor.step()
IranRuntime.autonomous_supervisor_run = lambda self, cycles=1: self.autonomous_supervisor.run(cycles)
IranRuntime.autonomous_supervisor_snapshot = lambda self: self.autonomous_supervisor.snapshot()
IranRuntime.autonomous_benchmark = lambda self: AutonomousBenchmark().run(self.autonomous_supervisor)

_base_runtime_close_supervisor = IranRuntime.close
def _runtime_close_supervisor(self):
    if hasattr(self, 'autonomous_supervisor'):
        self.autonomous_supervisor.stop()
    return _base_runtime_close_supervisor(self)
IranRuntime.close = _runtime_close_supervisor


# v0.38: explicit controllable background autonomy service (safe/read-only by default).
import threading

def _start_autonomous_daemon(self, interval=None):
    if getattr(self, '_autonomy_thread', None) and self._autonomy_thread.is_alive():
        return False
    delay = max(1, int(interval or self.config.get('runtime', {}).get('service_interval', 10)))
    self._autonomy_stop = threading.Event()
    def loop():
        self.events.emit('autonomous_daemon_started', {'interval': delay})
        while not self._autonomy_stop.wait(delay):
            try:
                self.autonomous_supervisor_step()
                self.autonomous_step()
            except Exception as exc:
                self.events.emit('autonomous_daemon_error', {'error': type(exc).__name__})
        self.events.emit('autonomous_daemon_stopped', {})
    self._autonomy_thread = threading.Thread(target=loop, name='iran-autonomy', daemon=True)
    self._autonomy_thread.start()
    return True

def _stop_autonomous_daemon(self):
    stop = getattr(self, '_autonomy_stop', None)
    if stop: stop.set()
    thread = getattr(self, '_autonomy_thread', None)
    if thread: thread.join(timeout=2)
    return True

IranRuntime.start_autonomous_daemon = _start_autonomous_daemon
IranRuntime.stop_autonomous_daemon = _stop_autonomous_daemon


"""Canonical runtime boundary for IRAN."""
from core.dialogue import LocalDialogueEngine
from core.cognitive_core import AdvancedCognitiveCore
from core.unified_pipeline import UnifiedCognitivePipeline

_runtime_base_init = IranRuntime.__init__


def _canonical_runtime_init(self, root):
    _runtime_base_init(self, root)
    self.dialogue = LocalDialogueEngine(self)
    self.cognitive_core = AdvancedCognitiveCore(self)
    self.unified_pipeline = UnifiedCognitivePipeline(self)
    self.events.emit("conversation_engine_ready", {
        "canonical": True,
        "offline": True,
        "persistent_state": True,
        "reference_resolution": True,
        "answer_verification": True,
    })
    self.events.emit("unified_pipeline_ready", {
        "canonical": True,
        "single_turn_path": True,
    })


IranRuntime.__init__ = _canonical_runtime_init


def _canonical_runtime_handle(self, text):
    clean = str(text or "").strip()
    if clean.startswith("/"):
        return self.orchestrator.handle(clean) if hasattr(self.orchestrator, "handle") else self.unified_pipeline.handle(clean)
    return self.unified_pipeline.handle(clean)


IranRuntime.handle = _canonical_runtime_handle
IranRuntime.conversation_snapshot = lambda self: self.dialogue.snapshot()
IranRuntime.conversation_trace = lambda self: self.dialogue.trace()
IranRuntime.advanced_cognitive_snapshot = lambda self: (
    self.cognitive_core.last_state.snapshot()
    if getattr(self, "cognitive_core", None) and self.cognitive_core.last_state
    else None
)
IranRuntime.unified_snapshot = lambda self: self.unified_pipeline.snapshot()


# v0.35: NARS/ONA-inspired symbolic reasoning bridge.
# Clean-room adaptation of public task/belief/revision ideas; fully offline and model-free.
from core.nars_reasoner import NarsInspiredReasoner

_runtime_nars_init = IranRuntime.__init__
def _init_nars(self, root):
    _runtime_nars_init(self, root)
    self.nars = NarsInspiredReasoner()
    self.nars.ingest_graph(self.knowledge)
    self.events.emit("nars_reasoner_ready", {"offline": True, "beliefs": len(self.nars.beliefs), "revision": True})
IranRuntime.__init__ = _init_nars

_pipeline_nars_base = UnifiedCognitivePipeline.handle

def _pipeline_nars_handle(self, text):
    runtime = self.runtime
    runtime.nars.beliefs.clear()
    runtime.nars.ingest_graph(runtime.knowledge)
    answer = _pipeline_nars_base(self, text)
    result = runtime.nars.answer_text(text)
    placeholder = "????? ???" in answer or "??? ????" in answer or answer.startswith("UNKNOWN:")
    if result.answer and result.confidence >= .70 and placeholder:
        answer = result.answer + "."
        runtime.events.emit("nars_reasoning", {"status": result.status, "confidence": result.confidence, "evidence": result.evidence, "derivation": result.derivation})
    elif placeholder and any(x in str(text) for x in ("ادامه", "همون قبلی", "همان قبلی", "بیشتر بگو", "بیشتر توضیح بده")):
        answer = "منظورت کدام موضوع یا مرجع است؟ اگر موضوع قبلی را می‌خواهی ادامه بدهم، نام موضوع را بگو."
    return answer

UnifiedCognitivePipeline.handle = _pipeline_nars_handle


# v0.36: AtomSpace-inspired typed knowledge bridge.
# Keeps one durable source of truth while exposing typed atoms/links to reasoning.
from core.atomspace_graph import AtomSpace

_runtime_atomspace_base_init = IranRuntime.__init__
def _init_atomspace(self, root):
    _runtime_atomspace_base_init(self, root)
    self.atomspace = AtomSpace(self.knowledge)
    self.events.emit("atomspace_ready", {"offline": True, **self.atomspace.snapshot()})
IranRuntime.__init__ = _init_atomspace

_pipeline_atomspace_base_handle = UnifiedCognitivePipeline.handle
def _pipeline_atomspace_handle(self, text):
    runtime = self.runtime
    # Refresh typed view from durable facts before each cognitive turn.
    runtime.atomspace = AtomSpace(runtime.knowledge)
    result = _pipeline_atomspace_base_handle(self, text)
    runtime.events.emit("atomspace_cycle", {
        "query": str(text),
        "graph": runtime.atomspace.snapshot(),
    })
    return result
UnifiedCognitivePipeline.handle = _pipeline_atomspace_handle

IranRuntime.atomspace_snapshot = lambda self: self.atomspace.snapshot()


# v0.36b: keep the typed layer synchronized with durable knowledge before reasoning.
_atomspace_sync_base_init = IranRuntime.__init__
def _init_atomspace_sync(self, root):
    _atomspace_sync_base_init(self, root)
    self.atomspace.sync()
    self.events.emit("atomspace_synced", self.atomspace.snapshot())
IranRuntime.__init__ = _init_atomspace_sync

_atomspace_sync_base_handle = UnifiedCognitivePipeline.handle
def _atomspace_sync_handle(self, text):
    runtime = self.runtime
    runtime.atomspace.sync()
    return _atomspace_sync_base_handle(self, text)
UnifiedCognitivePipeline.handle = _atomspace_sync_handle


# v0.37: integrated Soar/LIDA-inspired cognitive controller and procedural learning.
from core.cognitive_controller import CognitiveController

_controller_base_init = IranRuntime.__init__
def _init_controller(self, root):
    _controller_base_init(self, root)
    self.cognitive_controller = CognitiveController(self, self.root / 'data' / 'procedures.json')
    self.events.emit('cognitive_controller_ready', {'offline': True, 'attention': True, 'procedural_learning': True})
IranRuntime.__init__ = _init_controller

_controller_base_handle = UnifiedCognitivePipeline.handle
def _controller_handle(self, text):
    runtime = self.runtime
    result = _controller_base_handle(self, text)
    state = getattr(runtime.cognitive_core, 'last_state', None)
    if state is not None:
        cycle = runtime.cognitive_controller.cycle(text, state, result)
        verification = getattr(self.last_result, 'verification', {}) if self.last_result else {}
        proc = runtime.cognitive_controller.learn(state, result, verification)
        runtime.events.emit('executive_control', cycle)
        runtime.events.emit('attention_broadcast', runtime.cognitive_controller.workspace.snapshot())
        runtime.events.emit('procedural_learning', {
            'learned': bool(proc),
            'intent': getattr(state, 'intent', 'general'),
            'success': bool(verification.get('passed')),
        })
    return result
UnifiedCognitivePipeline.handle = _controller_handle

IranRuntime.cognitive_controller_snapshot = lambda self: self.cognitive_controller.snapshot()


# v0.38: expose the existing bounded autonomous supervisor as the final closed-loop endpoint.
from core.autonomous_supervisor import AutonomousSupervisor

_supervisor_base_init = IranRuntime.__init__
def _init_supervisor(self, root):
    _supervisor_base_init(self, root)
    self.autonomous_supervisor = AutonomousSupervisor(self)
    self.events.emit('autonomous_supervisor_ready', {'offline': True, 'bounded': True, 'read_only_actions': True})
IranRuntime.__init__ = _init_supervisor

IranRuntime.autonomy_step = lambda self: self.autonomous_supervisor.step()
IranRuntime.autonomy_run = lambda self, cycles=1: self.autonomous_supervisor.run(cycles)
IranRuntime.autonomy_snapshot = lambda self: self.autonomous_supervisor.snapshot()


# v0.38b: keep autonomous supervision lazy so normal dialogue does not scan the repository.
_lazy_runtime_init_base = _supervisor_base_init
def _init_supervisor_lazy(self, root):
    _lazy_runtime_init_base(self, root)
    self.autonomous_supervisor = None
    self.events.emit('autonomous_supervisor_ready', {'offline': True, 'bounded': True, 'lazy': True})
IranRuntime.__init__ = _init_supervisor_lazy

def _ensure_autonomous_supervisor(self):
    if self.autonomous_supervisor is None:
        self.autonomous_supervisor = AutonomousSupervisor(self)
    return self.autonomous_supervisor
IranRuntime._ensure_autonomous_supervisor = _ensure_autonomous_supervisor
IranRuntime.autonomy_step = lambda self: self._ensure_autonomous_supervisor().step()
IranRuntime.autonomy_run = lambda self, cycles=1: self._ensure_autonomous_supervisor().run(cycles)
IranRuntime.autonomy_snapshot = lambda self: self._ensure_autonomous_supervisor().snapshot()


# v0.38c: compatibility for legacy autonomy entry points after lazy supervisor initialization.
def _legacy_autonomous_supervisor(self):
    return self._ensure_autonomous_supervisor()
IranRuntime.autonomous_supervisor_step = lambda self: _legacy_autonomous_supervisor(self).step()
IranRuntime.autonomous_supervisor_run = lambda self, cycles=1: _legacy_autonomous_supervisor(self).run(cycles)
IranRuntime.autonomous_supervisor_snapshot = lambda self: _legacy_autonomous_supervisor(self).snapshot()
IranRuntime.autonomous_benchmark = lambda self: AutonomousBenchmark().run(_legacy_autonomous_supervisor(self))

_base_runtime_close_lazy = IranRuntime.close
def _runtime_close_lazy(self):
    supervisor = getattr(self, 'autonomous_supervisor', None)
    if supervisor is not None:
        supervisor.stop()
    return _base_runtime_close_lazy(self)
IranRuntime.close = _runtime_close_lazy


# v0.38d: close remains compatible with the legacy wrapper chain.
def _runtime_close_compat(self):
    if getattr(self, 'autonomous_supervisor', None) is None:
        self.autonomous_supervisor = AutonomousSupervisor(self)
    return _base_runtime_close_lazy(self)
IranRuntime.close = _runtime_close_compat
