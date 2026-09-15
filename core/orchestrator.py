import shlex
import time
import json
from planning.planner import Planner
from core.reasoning import Reasoner
from core.tool_router import ToolRouter
from core.agent_loop import AgentLoop
from core.intelligence import Intelligence
from core.cognition import Cognition
from core.metrics import Metrics
from core.language_engine import PersianLanguageEngine

class Orchestrator:
    """Executive coordinator: cognition -> tools/plans -> local response -> evidence."""
    def __init__(self,agent,memory,events,registry=None,policy=None,goals=None,evaluator=None):
        self.agent,self.memory,self.events=agent,memory,events; self.registry=registry; self.policy=policy; self.goals=goals
        self.planner,self.reasoner=Planner(),Reasoner(); self.router,self.intelligence=ToolRouter(),Intelligence(); self.cognition=Cognition(); self.metrics=Metrics(); self.evaluator=evaluator
        self.language=getattr(getattr(agent,'brain',None),'language',PersianLanguageEngine()); self.loop=AgentLoop(self,max_attempts=3)

    def run_tool(self,name,**kwargs):
        tool=self.registry.get(name) if self.registry else None
        if not tool: raise KeyError(f'unknown tool: {name}')
        if self.policy and not self.policy.allows(tool.permission): raise PermissionError(f'permission denied: {tool.permission}')
        result=self.registry.run(name,**kwargs); self.events.emit('tool_executed',{'tool':name,'ok':True}); self.metrics.record('tool'); return result

    def _parse_tool(self,text):
        parts=shlex.split(text)
        if len(parts)<2: raise ValueError('usage: /tool NAME [key=value ...]')
        kwargs={}
        for item in parts[2:]:
            if '=' not in item: raise ValueError(f'argument must use key=value: {item}')
            k,v=item.split('=',1); kwargs[k]=int(v) if v.isdigit() else v
        return parts[1],kwargs

    def _parse_verified_run(self, text):
        """Parse an explicit, permission-gated verified task request.

        Syntax: /run GOAL --tool NAME --expected VALUE [--alternative NAME]
        [--arg key=value ...].  Plain /run keeps the legacy agent loop.
        """
        parts=shlex.split(text)
        if len(parts)<2 or '--tool' not in parts:
            return None
        try:
            tool=parts[parts.index('--tool')+1]
            expected=parts[parts.index('--expected')+1]
        except (ValueError, IndexError) as exc:
            raise ValueError('usage: /run GOAL --tool NAME --expected VALUE [--alternative NAME] [--arg key=value]') from exc
        alternative=None
        if '--alternative' in parts:
            index=parts.index('--alternative')
            try: alternative=parts[index+1]
            except IndexError as exc: raise ValueError('missing value for --alternative') from exc
        tool_index=parts.index('--tool')
        goal=' '.join(parts[1:tool_index]).strip()
        kwargs={}
        i=0
        while i < len(parts):
            if parts[i]=='--arg':
                if i+1>=len(parts) or '=' not in parts[i+1]:
                    raise ValueError('--arg requires key=value')
                key,value=parts[i+1].split('=',1)
                kwargs[key]=int(value) if value.isdigit() else value
                i+=2
                continue
            i+=1
        if not goal: raise ValueError('verified run requires a goal')
        return {'goal':goal,'primary':tool,'alternative':alternative,
                'expected_effect':expected,'kwargs':kwargs}

    def _format_verified_result(self, result):
        task=result.get('task') or {}
        status=task.get('status','unknown') if isinstance(task,dict) else 'unknown'
        verified=result.get('alternative') or result.get('primary') or {}
        return (f"task={status}; verified={bool(verified.get('success'))}; "
                f"reason={verified.get('reason','unknown')}; "
                f"task_id={task.get('task_id','unknown') if isinstance(task,dict) else 'unknown'}")

    def _auto_tool(self,text):
        name,kwargs=self.router.choose(text)
        if not name:return None
        result=self.run_tool(name,**kwargs)
        labels={'time_now':'زمان سیستم','project_summary':'خلاصه پروژه','system_info':'مشخصات سیستم','project_files':'فایل‌های پروژه','memory_search':'حافظه مرتبط'}
        return f"{labels.get(name,name)}: {result}"

    def execute_plan(self,plan):
        for step in plan.steps: step.status='done'; step.result='locally acknowledged'
        plan.status='completed'; self.events.emit('plan_completed',{'goal':plan.goal,'steps':len(plan.steps)})

    def handle(self,text):
        started=time.perf_counter(); clean=str(text).strip()
        if not clean:return 'چیزی برای پردازش دریافت نکردم.'
        brain=getattr(self.agent,'brain',None); language=brain.analyze(clean) if brain else self.language.analyze(clean)
        cognitive=self.cognition.analyze(clean); self.memory.add('semantic_input',json.dumps({'intent':language.intent,'goal':language.goal,'entities':language.entities},ensure_ascii=False),.55)
        decision=self.intelligence.decide(clean)
        self.events.emit('goal_received',{'goal':clean,'intent':cognitive.intent,'language_intent':language.intent,'confidence':max(cognitive.confidence,language.confidence),'needs_model':cognitive.needs_model})
        if clean.startswith('/run '):
            verified=self._parse_verified_run(clean)
            if verified is not None:
                executor=getattr(self,'verified_executor',None)
                if executor is None:
                    raise RuntimeError('verified task execution is not connected')
                result=executor(**verified)
                return self._format_verified_result(result)
            return self.loop.run(clean[5:].strip()).answer
        if clean.startswith('/tool '):
            name,kwargs=self._parse_tool(clean); return str(self.run_tool(name,**kwargs))
        if clean.startswith('/goal '): return str(self.goals.add(clean[6:].strip()) if self.goals else 'Goal store unavailable.')
        if clean.startswith('/complete '): return str(self.goals.complete(clean.split(maxsplit=1)[1]) if self.goals else 'Goal not found.')
        if clean.startswith('/reason '): return str(self.reasoner.analyze(clean[8:].strip(),self.memory.working_context(clean,6)))
        auto=self._auto_tool(clean)
        if auto is not None:
            self.memory.add('tool_result',auto,.75); self.metrics.record('auto_tool',time.perf_counter()-started); return auto
        plan=self.planner.build(clean,brain.analyze(clean) if brain else None); answer=self.agent.respond(clean); self.execute_plan(plan)
        self.events.emit('response_generated',{'goal':clean,'intent':cognitive.intent,'decision':decision.actions})
        self.metrics.record('response',time.perf_counter()-started); return answer

    def explain_decision(self,text):
        c=self.cognition.analyze(text); d=self.intelligence.decide(text); return {'intent':c.intent,'confidence':c.confidence,'needs_model':c.needs_model,'goals':c.goals,'actions':d.actions,'reasons':c.reasons}
    def run_smart(self,goal): return self.loop.run(goal)


# v0.31: make persistent User Model an executive input, not passive metadata.
def _user_model_context(self, text):
    model = getattr(self, '_user_model', None)
    if model is None and getattr(self, 'agent', None) is not None:
        model = getattr(self.agent, '_user_model', None)
    if model is None:
        return []
    try:
        facts = model.facts(limit=12)
        return [
            ('user_model', f"{f['predicate']}={f['object']} confidence={float(f['confidence']):.2f} source={f['source']}")
            for f in facts
        ]
    except Exception:
        return []

if not hasattr(Orchestrator, '_iran_v31_handle_base'):
    Orchestrator._iran_v31_handle_base = Orchestrator.handle
_base_v31_handle = Orchestrator._iran_v31_handle_base

def _handle_v31(self, text):
    model = getattr(self.agent, '_user_model', None)
    if model is not None:
        self._user_model = model
    return _base_v31_handle(self, text)

Orchestrator.handle = _handle_v31

if not hasattr(Orchestrator, '_iran_v31_explain_base'):
    Orchestrator._iran_v31_explain_base = Orchestrator.explain_decision
_base_v31_explain = Orchestrator._iran_v31_explain_base

def _explain_v31(self, text):
    context = self.memory.working_context(text, 6)
    context = list(context) + self._user_model_context(text)
    r = self.reasoner.analyze(text, context)
    d = self.intelligence.decide(text)
    c = self.cognition.analyze(text)
    return {'intent':c.intent,'confidence':c.confidence,'needs_model':c.needs_model,
            'goals':c.goals,'actions':d.actions,'reasons':c.reasons,
            'user_model':self._user_model_context(text),
            'reasoning':r.__dict__}

Orchestrator.explain_decision = _explain_v31


# v0.31b: bind the persistent User Model into the Planner after runtime initialization.
if not hasattr(Orchestrator, '_iran_v31_init_base'):
    Orchestrator._iran_v31_init_base = Orchestrator.__init__
_base_v31_init_orch = Orchestrator._iran_v31_init_base

def _init_v31_orch(self, *args, **kwargs):
    _base_v31_init_orch(self, *args, **kwargs)
    model = getattr(self.agent, '_user_model', None)
    if model is not None:
        self._user_model = model
        self.planner.user_model = model

Orchestrator.__init__ = _init_v31_orch


# v0.31c: bind User Model to Reasoner for explicit evidence-aware analysis.
if not hasattr(Orchestrator, '_iran_v31c_init_base'):
    Orchestrator._iran_v31c_init_base = Orchestrator.__init__
_base_v31c_init = Orchestrator._iran_v31c_init_base

def _init_v31c(self, *args, **kwargs):
    _base_v31c_init(self, *args, **kwargs)
    model = getattr(self.agent, '_user_model', None)
    if model is not None:
        self._user_model = model
        self.planner.user_model = model
        self.reasoner.user_model = model

Orchestrator.__init__ = _init_v31c


# v0.31d: expose the context helper as an Orchestrator method.
Orchestrator._user_model_context = _user_model_context


# v0.31d: ensure User Model context is always available to decision explanation.
# This compatibility binding is intentionally small and avoids another wrapper chain.
if not hasattr(Orchestrator, '_user_model_context'):
    def _compat_user_model_context(self, text):
        model = getattr(self, '_user_model', None) or getattr(getattr(self, 'agent', None), '_user_model', None)
        if model is None:
            return []
        try:
            return [('user_model', f"{f['predicate']}={f['object']} confidence={float(f['confidence']):.2f} source={f['source']}")
                    for f in model.facts(limit=12)]
        except Exception:
            return []
    Orchestrator._user_model_context = _compat_user_model_context
