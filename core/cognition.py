from dataclasses import dataclass, field
import re

@dataclass
class CognitivePlan:
    intent: str
    confidence: float
    goals: list[str] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    needs_model: bool = False
    reasons: list[str] = field(default_factory=list)

class Cognition:
    """Task understanding layer: intent, entities, decomposition and tool strategy."""
    def analyze(self, text):
        t=str(text).strip(); low=t.lower()
        if not t: return CognitivePlan('empty',1.0)
        intent='conversation'; needs_model=True; actions=[]; reasons=[]
        patterns=[('time',r'ساعت|زمان|تاریخ'),('system',r'مشخصات.*(سیستم|کامپیوتر)|cpu|ram|رم'),
                  ('project',r'پروژه|ساختار|فایل(?:ها|‌ها)?'),('memory',r'یادت|قبلا|قبلاً|چی گفتم|حافظه'),
                  ('web',r'اینترنت|وب|سایت|url|http'),('planning',r'برنامه.?ریزی|پلن|هدف|قدم.?ها|مراحل'),
                  ('build',r'بساز|ایجاد کن|پیاده.?سازی|توسعه|build|create'),('debug',r'خطا|باگ|debug|مشکل|کار نمی.?کنه')]
        for name,pat in patterns:
            if re.search(pat,low): intent=name; needs_model=name in {'planning','build','debug'}; reasons.append('matched:'+name); break
        if '?' in t or '؟' in t or re.search(r'چرا|چطور|چگونه',low): needs_model=True
        goals=[g.strip() for g in re.split(r'\s*(?:و سپس|بعد|سپس|؛|;|\n)\s*',t) if g.strip()]
        return CognitivePlan(intent,0.96 if intent!='conversation' else 0.72,goals,actions,needs_model,reasons)
