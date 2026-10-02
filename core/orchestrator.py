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
        self._user_model = getattr(agent, "_user_model", None)

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
        canonical = getattr(self, "_canonical_system", None)
        if canonical is None:
            raise RuntimeError("Orchestrator.handle is a compatibility adapter; bind CognitiveSystem first")
        return canonical.dispatch(text)


    def _user_model_context(self, text):
        model = getattr(self, '_user_model', None) or getattr(getattr(self, 'agent', None), '_user_model', None)
        if model is None:
            return []
        try:
            return [('user_model', f"{f['predicate']}={f['object']} confidence={float(f['confidence']):.2f} source={f['source']}")
                    for f in model.facts(limit=12)]
        except Exception:
            return []

    def explain_decision(self,text):
        c=self.cognition.analyze(text); d=self.intelligence.decide(text)
        return {'intent':c.intent,'confidence':c.confidence,'needs_model':c.needs_model,
                'goals':c.goals,'actions':d.actions,'reasons':c.reasons,
                'user_model':self._user_model_context(text)}

    def run_smart(self,goal):
        canonical = getattr(self, "_canonical_system", None)
        if canonical is None:
            raise RuntimeError("Orchestrator.run_smart is a compatibility adapter; bind CognitiveSystem first")
        return canonical.dispatch(str(goal))
