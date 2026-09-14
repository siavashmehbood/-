from dataclasses import dataclass, field
from time import perf_counter

@dataclass
class Decision:
    goal: str
    intent: str
    confidence: float
    actions: list = field(default_factory=list)
    reasons: list = field(default_factory=list)

class Intelligence:
    """Fast deterministic executive layer before the model/tool layer."""
    def classify(self, text):
        t = str(text).strip().lower()
        if not t: return 'empty'
        if t.startswith('/'): return 'command'
        if any(x in t for x in ('ساعت','زمان','تاریخ')): return 'system_time'
        if any(x in t for x in ('فایل','ساختار پروژه','پروژه')): return 'project_inspection'
        if any(x in t for x in ('کامپیوتر','سیستم','رم','cpu','پردازنده')): return 'system_info'
        if any(x in t for x in ('یادت','قبلا','قبلًا','چی گفتم')): return 'memory_recall'
        if any(x in t for x in ('برنامه','برنامه‌ریزی','پلن','هدف')): return 'planning'
        if any(x in t for x in ('چطور','چگونه','چیکار','چی کار')): return 'question'
        return 'conversation'

    def decide(self, goal):
        started = perf_counter()
        intent = self.classify(goal)
        actions = {
            'system_time':['time_now'], 'project_inspection':['project_summary'],
            'system_info':['system_info'], 'memory_recall':['memory_search'],
            'planning':['planner']
        }.get(intent, [])
        confidence = 0.95 if actions else 0.70
        return Decision(goal, intent, confidence, actions, [f'classified:{intent}', f'latency_ms:{(perf_counter()-started)*1000:.3f}'])
