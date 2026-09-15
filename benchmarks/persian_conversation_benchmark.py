from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    turns: tuple[str, ...]
    checks: tuple[str, ...]


class PersianConversationBenchmark:
    """100 deterministic local dialogue scenarios; no network or model dependency."""
    def scenarios(self):
        base = [
            Scenario('greeting', ('سلام',), ('سلام',)),
            Scenario('identity', ('اسمت چیه؟',), ('IRAN',)),
            Scenario('python_followup', ('پایتون چیه؟', 'چرا؟', 'برای پروژه من خوبه؟'), ('پایتون', 'محبوب', 'پروژه')),
            Scenario('reference', ('حافظه چیه؟', 'این بخش رو بهتر کن.'), ('حافظه',)),
            Scenario('correction', ('این بخش رو توضیح بده.', 'نه، منظورم حافظه بود.'), ('حافظه', 'اصلاح')),
            Scenario('topic_restore', ('پایتون چیه؟', 'حافظه چیه؟', 'موضوع قبلی رو ادامه بده.'), ('پایتون',)),
            Scenario('unknown', ('آیا فردا ساعت ۸ باران می‌بارد؟',), ('اطلاعات',)),
            Scenario('multi', ('پایتون چیه و چرا محبوبه و برای پروژه من چه فایده‌ای داره؟',), ('پایتون', 'چرا', 'پروژه')),
            Scenario('short_followup', ('پایتون چیه؟', 'خب؟', 'بیشتر بگو.'), ('پایتون',)),
            Scenario('style', ('پایتون چیه؟', 'ساده‌تر بگو.', 'کوتاه‌تر بگو.'), ('پایتون',)),
        ]
        scenarios = []
        for i in range(10):
            for item in base:
                scenarios.append(Scenario(f'{item.name}_{i+1}', item.turns, item.checks))
        return scenarios

    def run(self, runtime):
        results = []
        for scenario in self.scenarios():
            outputs = []
            passed = True
            for turn in scenario.turns:
                answer = str(runtime.handle(turn))
                outputs.append(answer)
            joined = '\n'.join(outputs)
            for check in scenario.checks:
                if check not in joined:
                    passed = False
            results.append({'name': scenario.name, 'passed': passed, 'outputs': outputs})
        passed = sum(1 for r in results if r['passed'])
        return {'score': round(passed / len(results) * 100, 2), 'passed': passed, 'total': len(results), 'results': results}
