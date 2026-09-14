from dataclasses import dataclass,field
from typing import List
@dataclass
class PlanStep:
    id:int; title:str; status:str='pending'; result:str=''; risk:float=.1; depends_on:list[int]=field(default_factory=list); success_criteria:str=''
@dataclass
class Plan:
    goal:str; steps:List[PlanStep]=field(default_factory=list); status:str='draft'; assumptions:List[str]=field(default_factory=list); strategy:str='safe-first'; version:int=1
class Planner:
    """Adaptive dependency-aware planner with verification gates, rollback and replanning."""
    def build(self,goal,state=None):
        clean=str(goal).strip()
        if not clean:return Plan('',[],'empty')
        intent=getattr(state,'intent','general') if state else 'general'
        if intent=='debug' or any(x in clean.lower() for x in ('خطا','باگ','کار نمی‌کند','debug')):titles=['بازسازی خطا','جمع‌آوری شواهد','جداسازی علت‌ها','آزمایش کم‌ریسک','تأیید رفع']
        elif intent=='build' or any(x in clean.lower() for x in ('بساز','ایجاد','پیاده','build')):titles=['تعریف خروجی و معیار','بررسی اجزای موجود','طراحی کوچک‌ترین هسته','پیاده‌سازی محدود','تست']
        elif intent in ('planning','plan'):titles=['تعریف هدف','استخراج محدودیت','تولید گزینه','تحلیل ریسک/فایده','انتخاب استراتژی']
        elif intent in ('inspection','inspect'):titles=['جمع‌آوری وضعیت','اندازه‌گیری','تشخیص ناهنجاری','اعتبارسنجی','گزارش و اقدام']
        else:titles=['فهم درخواست','بازیابی زمینه','جمع‌آوری شواهد','اقدام امن','ارزیابی نتیجه']
        steps=[PlanStep(i+1,title,risk=min(.75,.08+.07*i),depends_on=[i] if i>0 else [],success_criteria='نتیجه قابل مشاهده و قابل ارزیابی') for i,title in enumerate(titles)]
        return Plan(clean,steps,'ready',[],'evidence-first',1)
    def next_ready(self,plan):
        done={s.id for s in plan.steps if s.status=='done'};return [s for s in plan.steps if s.status=='pending' and all(d in done for d in s.depends_on)]
    def complete(self,plan,step_id,result,success=True):
        for step in plan.steps:
            if step.id==int(step_id):step.status='done' if success else 'failed';step.result=str(result)
        plan.status='complete' if all(s.status=='done' for s in plan.steps) else 'running';return plan
    def replan(self,plan,failed_step,observation=''):
        idx=max(0,min(len(plan.steps)-1,int(failed_step)-1)) if plan.steps else 0
        for step in plan.steps[idx:]:step.status='pending'
        if plan.steps:plan.steps[idx].result=str(observation);plan.status='replanned';plan.version+=1
        return plan
    def rollback(self,plan):
        for step in plan.steps:
            if step.status=='done' and step.risk>.45:step.status='rollback-required'
        plan.status='rollback-review';return plan
    def summary(self,plan):
        return '\n'.join([f'Goal: {plan.goal}',f'Status: {plan.status}',f'Strategy: {plan.strategy}',f'Version: {plan.version}']+[f'{s.id}. [{s.status}] {s.title} risk={s.risk:.2f} deps={s.depends_on}' for s in plan.steps])

# v0.22: plans carry explicit constraints, gates and observable success conditions.
def _build_v2(self,goal,state=None):
    clean=str(goal).strip(); intent=getattr(state,'intent','general') if state else 'general'
    constraints=[]
    for marker in ('بدون','نباید','فقط','حتماً','حداقل','حداکثر','ترجیحاً'):
        if marker in clean: constraints.append(clean[clean.find(marker):].split('،')[0].strip())
    if any(x in clean.lower() for x in ('بساز','پیاده','توسعه','اضافه')): titles=['تعریف خروجی','بررسی وضعیت فعلی','طراحی تغییر حداقلی','پیاده‌سازی','تست واحد','تست یکپارچه','ارزیابی','ثبت/یادگیری']
    elif intent=='debug' or 'خطا' in clean.lower(): titles=['بازتولید','ثبت شواهد','تفکیک فرضیه‌ها','آزمایش کم‌ریسک','تأیید رفع','رگرسیون']
    elif intent in ('plan','planning'): titles=['هدف','محدودیت','گزینه‌ها','معیارها','ریسک','انتخاب','آزمون','بازنگری']
    else: titles=['فهم هدف','بازیابی زمینه','شواهد','گزینه‌ها','اقدام','مشاهده','ارزیابی','یادگیری']
    steps=[]
    for i,title in enumerate(titles):
        dep=[i] if i else []; risk=min(.75,.06+.06*i)
        crit='خروجی قابل مشاهده ثبت شود؛ در شکست، مرحله بعدی متوقف و برنامه بازسازی شود.'
        steps.append(PlanStep(i+1,title,'pending','',risk,dep,crit))
    return Plan(clean,steps,'ready',constraints,'evidence-first',1)
Planner.build=_build_v2

# Compatibility gate: keep five top-level plan stages while each stage can represent a richer internal phase.
def _build_v3(self,goal,state=None):
    clean=str(goal).strip(); intent=getattr(state,'intent','general') if state else 'general'; constraints=[]
    for marker in ('بدون','نباید','فقط','حتماً','حداقل','حداکثر','ترجیحاً'):
        if marker in clean: constraints.append(clean[clean.find(marker):].split('،')[0].strip())
    if intent=='debug': titles=['بازتولید و شواهد','تفکیک علت‌ها','آزمایش کم‌ریسک','تأیید رفع','رگرسیون و یادگیری']
    elif intent in ('build','planning','plan') or any(x in clean.lower() for x in ('بساز','پیاده','توسعه')): titles=['هدف و معیار','بررسی و طراحی','پیاده‌سازی مرحله‌ای','تست و اعتبارسنجی','ارزیابی و یادگیری']
    else: titles=['فهم هدف','زمینه و شواهد','اقدام','مشاهده نتیجه','ارزیابی و یادگیری']
    steps=[]
    for i,title in enumerate(titles):
        dep=[i] if i else []; risk=min(.7,.08+.08*i); crit='خروجی قابل مشاهده ثبت شود؛ شکست باعث بازبرنامه‌ریزی می‌شود.'
        steps.append(PlanStep(i+1,title,'pending','',risk,dep,crit))
    return Plan(clean,steps,'ready',constraints,'evidence-first',1)
Planner.build=_build_v3

# Preserve the established public plan contract while retaining richer semantics.
def _build_v4(self,goal,state=None):
    clean=str(goal).strip(); intent=getattr(state,'intent','general') if state else 'general'; constraints=[]
    for marker in ('بدون','نباید','فقط','حتماً','حداقل','حداکثر','ترجیحاً'):
        if marker in clean: constraints.append(clean[clean.find(marker):].split('،')[0].strip())
    if intent=='debug': titles=['بازسازی و تعریف خطا','جمع‌آوری و تفکیک شواهد','آزمایش کم‌ریسک علت','تأیید رفع و کنترل','رگرسیون و یادگیری']
    elif intent in ('build','planning','plan') or any(x in clean.lower() for x in ('بساز','پیاده','توسعه')): titles=['تعریف هدف و معیار','بررسی و طراحی','پیاده‌سازی مرحله‌ای','تست و اعتبارسنجی','ارزیابی و یادگیری']
    else: titles=['تعریف هدف','جمع‌آوری زمینه و شواهد','اقدام قابل بازگشت','مشاهده نتیجه','ارزیابی و یادگیری']
    steps=[PlanStep(i+1,t,'pending','',min(.7,.08+.08*i),[i] if i else [],'خروجی قابل مشاهده ثبت شود؛ شکست باعث بازبرنامه‌ریزی می‌شود.') for i,t in enumerate(titles)]
    return Plan(clean,steps,'ready',constraints,'evidence-first',1)
Planner.build=_build_v4


# v0.31: carry explicit User Model facts into plan assumptions/strategy.
if not hasattr(Planner, '_iran_v31_build_base'):
    Planner._iran_v31_build_base = Planner.build
_base_v31_build = Planner._iran_v31_build_base

def _build_v31(self, goal, state=None):
    plan = _base_v31_build(self, goal, state)
    facts = getattr(state, '_user_model_facts', []) if state is not None else []
    facts = facts if isinstance(facts, list) else []
    for fact in facts[:8]:
        text = f"user.{fact.get('predicate')}={fact.get('object')}"
        if text not in plan.assumptions:
            plan.assumptions.append(text)
    if facts:
        plan.strategy = 'evidence-first + user-context-aware'
    return plan

Planner.build = _build_v31


# v0.31b: Planner keeps a direct read-only link to the runtime User Model.
if not hasattr(Planner, '_iran_v31_init_base'):
    Planner._iran_v31_init_base = Planner.__init__
_base_v31_init = Planner._iran_v31_init_base

def _init_v31(self, *args, **kwargs):
    _base_v31_init(self, *args, **kwargs)
    self.user_model = None

Planner.__init__ = _init_v31

if not hasattr(Planner, '_iran_v31b_build_base'):
    Planner._iran_v31b_build_base = Planner.build
_base_v31b_build = Planner._iran_v31b_build_base

def _build_v31b(self, goal, state=None):
    plan = _base_v31b_build(self, goal, state)
    model = getattr(self, 'user_model', None)
    if model is not None:
        try:
            for f in model.facts(limit=8):
                item = f"user.{f['predicate']}={f['object']}"
                if item not in plan.assumptions:
                    plan.assumptions.append(item)
            plan.strategy = 'evidence-first + user-context-aware'
        except Exception:
            pass
    return plan

Planner.build = _build_v31b
