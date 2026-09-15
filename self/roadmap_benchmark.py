from dataclasses import dataclass, field


@dataclass
class CaseResult:
    name: str
    passed: bool
    answer: str
    expected: str


@dataclass
class RoadmapBenchmarkResult:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def passed(self):
        return bool(self.cases) and all(item.passed for item in self.cases)

    @property
    def score(self):
        return round(sum(item.passed for item in self.cases) / max(1, len(self.cases)), 3)


class PersianRoadmapBenchmark:
    def run(self, runtime):
        cases = []
        def ask(name, text, expected, predicate):
            answer = str(runtime.handle(text))
            cases.append(CaseResult(name, bool(predicate(answer)), answer, expected))
        ask('factual', 'پایتخت ایران کجاست؟', 'تهران', lambda x: 'تهران' in x)
        ask('unknown', 'دمای دقیق هسته مشتری در سال ۱۴۲۰ چقدر است؟', 'UNKNOWN', lambda x: 'UNKNOWN' in x)
        ask('clarification', 'همون قبلی رو ادامه بده.', 'CLARIFICATION', lambda x: 'موضوع' in x or 'مرجع' in x)
        runtime.handle('موضوع اصلی ما معماری شناختی ایران است.')
        ask('reference', 'همون قبلی رو ادامه بده.', 'معماری شناختی ایران', lambda x: 'معماری شناختی ایران' in x)
        ask('why', 'چرا سیستم کند است؟', 'علت و گام تشخیصی', lambda x: len(x) > 80 and ('علت' in x or 'گلوگاه' in x))
        ask('how', 'چطور حافظه را بهتر کنیم؟', 'مراحل', lambda x: len(x) > 80 and ('مراحل' in x or 'مسیر' in x or 'گام' in x))
        ask('comparison', 'حافظه episodic بهتر است یا semantic؟', 'معیار مقایسه', lambda x: 'معیار' in x or 'انتخاب' in x)
        ask('feedback', 'این پاسخ درست بود.', 'بازخورد', lambda x: 'بازخورد' in x)
        return RoadmapBenchmarkResult(cases)
