"""Deterministic 100-scenario Persian conversation benchmark.

Each scenario starts from a clean runtime root, so scenarios cannot leak topic
state into one another and results are independent of execution order. Turns are
typed tuples: a scenario's `turns` that is a bare string is iterated
character-by-character instead of turn-by-turn, so the scenario builder below
fails loudly on malformed input rather than silently scoring it.
"""
from dataclasses import dataclass

TURN_CHECKS = (
    ('greeting', ('سلام',), ('سلام',)),
    ('identity', ('اسمت چیه؟',), ('ایران',)),
    ('python_followup', ('پایتون چیه؟', 'چرا؟', 'برای پروژه من خوبه؟'), ('پایتون', 'محبوب', 'پروژه')),
    ('reference', ('حافظه چیه؟', 'این بخش رو بهتر کن.'), ('حافظه',)),
    ('correction', ('این بخش رو توضیح بده.', 'نه، منظورم حافظه بود.'), ('حافظه', 'متوجه')),
    ('topic_restore', ('پایتون چیه؟', 'حافظه چیه؟', 'موضوع قبلی رو ادامه بده.'), ('پایتون',)),
    ('unknown', ('آیا فردا ساعت ۸ باران میبارد؟',), ('اطلاعات', 'کافی', 'نمی')),
    ('multi', ('پایتون چیه و چرا محبوبه و برای پروژه من چه فایدهای داره؟',), ('پایتون', 'محبوب', 'پروژه')),
    ('short_followup', ('پایتون چیه؟', 'خب؟', 'بیشتر بگو.'), ('پایتون',)),
    ('style', ('پایتون چیه؟', 'ساده‌تر بگو.', 'کوتاه‌تر بگو.'), ('پایتون',)),
)


@dataclass(frozen=True)
class Scenario:
    name: str
    turns: tuple
    checks: tuple


class PersianConversationBenchmark:
    """100 deterministic local dialogue scenarios; no network or model dependency."""

    def scenarios(self):
        return [
            Scenario(f'{name}_{i + 1}', turns, checks)
            for i in range(10)
            for name, turns, checks in TURN_CHECKS
        ]

    def run(self, runtime_factory):
        results = []
        for scenario in self.scenarios():
            if isinstance(scenario.turns, str):
                raise TypeError(f'scenario {scenario.name} has a string `turns`; it must be a tuple of turns')
            local = runtime_factory()
            try:
                outputs = [str(local.handle(turn)) for turn in scenario.turns]
            finally:
                local.close()
            joined = '\n'.join(outputs).lower()
            passed = all(check.lower() in joined for check in scenario.checks)
            results.append({'name': scenario.name, 'passed': passed, 'outputs': outputs})
        passed = sum(1 for r in results if r['passed'])
        return {'score': round(passed / len(results) * 100, 2), 'passed': passed, 'total': len(results), 'results': results}
