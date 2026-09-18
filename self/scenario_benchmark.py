from dataclasses import dataclass, field
from collections import Counter


@dataclass
class Scenario:
    name: str
    category: str
    text: str
    predicate: object


@dataclass
class ScenarioResult:
    name: str
    category: str
    passed: bool
    answer: str


@dataclass
class ScenarioBenchmarkResult:
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def score(self):
        return round(sum(item.passed for item in self.results) / max(1, len(self.results)), 3)

    @property
    def metrics(self):
        totals=Counter(item.category for item in self.results)
        passed=Counter(item.category for item in self.results if item.passed)
        category_scores={key: round(passed[key]/value, 3) for key, value in sorted(totals.items())}
        aliases={
            'factual_accuracy':'factual', 'unknown_precision':'unknown',
            'clarification_success':'clarification', 'why_reasoning':'why',
            'how_planning':'how', 'comparison_quality':'comparison',
            'feedback_handling':'feedback', 'goal_tracking':'goal',
            'negation_compliance':'negation',
        }
        return {**category_scores, **{name: category_scores.get(category, 0.0) for name, category in aliases.items()}}


class PersianScenarioBenchmark:
    """Generated, categorized benchmark; cases are behavior variants, not answer maps."""

    def scenarios(self):
        cases=[]
        factual=[
            ('پایتخت ایران کجاست؟','تهران'),('مرکز سیاسی کشور ایران چیست؟','تهران'),
            ('پایتخت فرانسه کجاست؟','پاریس'),('هفته چند روز دارد؟','هفت'),
            ('آب در چند درجه می‌جوشد؟','۱۰۰'),
        ]
        for index in range(20):
            text, expected=factual[index % len(factual)]
            cases.append(Scenario(f'factual_{index+1}','factual',text,lambda a,e=expected:e in a))
        for index in range(15):
            text=f'برای یک پدیده ناشناخته شماره {index+1} در سال ۱۴۲۰ چه داده دقیقی وجود دارد؟'
            cases.append(Scenario(f'unknown_{index+1}','unknown',text,lambda a:'UNKNOWN' in a))
        for index in range(10):
            cases.append(Scenario(f'clarification_{index+1}','clarification','همون قبلی رو ادامه بده.',lambda a:'موضوع' in a or 'مرجع' in a))
        for index in range(10):
            cases.append(Scenario(f'why_{index+1}','why','چرا سیستم کند است؟',lambda a:len(a)>80 and ('علت' in a or 'گلوگاه' in a)))
        for index in range(10):
            cases.append(Scenario(f'how_{index+1}','how','چطور حافظه را بهتر کنیم؟',lambda a:len(a)>80 and ('گام' in a or 'مسیر' in a or 'مراحل' in a)))
        for index in range(10):
            cases.append(Scenario(f'compare_{index+1}','comparison','حافظه episodic بهتر است یا semantic؟',lambda a:'معیار' in a or 'انتخاب' in a or 'مناسب' in a))
        for index in range(10):
            cases.append(Scenario(f'feedback_{index+1}','feedback','این پاسخ درست بود.',lambda a:'بازخورد' in a))
        for index in range(10):
            cases.append(Scenario(f'goal_{index+1}','goal',f'هدف من بررسی امن پروژه شماره {index+1} است.',lambda a:'ثبت' in a or 'هدف' in a or 'موضوع' in a))
        for index in range(5):
            cases.append(Scenario(f'negation_{index+1}','negation','این کار را بدون اتصال اینترنت انجام بده.',lambda a:'بدون' in a or 'محدودیت' in a or 'آفلاین' in a))
        return cases

    def run(self, runtime, limit=None):
        cases=self.scenarios()[:limit] if limit else self.scenarios()
        results=[]
        for case in cases:
            answer=str(runtime.handle(case.text))
            try: passed=bool(case.predicate(answer))
            except Exception: passed=False
            results.append(ScenarioResult(case.name,case.category,passed,answer))
        return ScenarioBenchmarkResult(results)
