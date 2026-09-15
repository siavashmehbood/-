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
            Scenario('identity', ('اسمت چیه؟',), ('ایران',)),
            Scenario('python_followup', ('پایتون چیه؟', 'چرا؟', 'برای پروژه من خوبه؟'), ('پایتون', 'محبوب', 'پروژه')),
            Scenario('reference', ('حافظه چیه؟', 'این بخش رو بهتر کن.'), ('حافظه',)),
            Scenario('correction', ('این بخش رو توضیح بده.', 'نه، منظورم حافظه بود.'), ('حافظه', 'متوجه')),
            Scenario('topic_restore', ('پایتون چیه؟', 'حافظه چیه؟', 'موضوع قبلی رو ادامه بده.'), ('پایتون',)),
            Scenario('unknown', ('آیا فردا ساعت ۸ باران می‌بارد؟',), ('اطلاعات', 'کافی', 'نمی')),
            Scenario('multi', ('پایتون چیه و چرا محبوبه و برای پروژه من چه فایده‌ای داره؟'), ('پایتون', 'محبوب', 'پروژه')),
            Scenario('short_followup', ('پایتون چیه؟', 'خب؟', 'بیشتر بگو.'), ('پایتون',)),
            Scenario('style', ('پایتون چیه؟', 'ساده‌تر بگو.', 'کوتاه‌تر بگو.'), ('پایتون',)),
        ]
        return [Scenario(f'{item.name}_{i+1}', item.turns, item.checks) for i in range(10) for item in base]

    def run(self, runtime):
        results=[]
        root=getattr(runtime,'root',None)
        runtime_cls=runtime.__class__
        for scenario in self.scenarios():
            local=runtime_cls(root) if root is not None else runtime
            try:
                outputs=[str(local.handle(turn)) for turn in scenario.turns]
            finally:
                if local is not runtime:
                    local.close()
            joined='\n'.join(outputs).lower()
            passed=all(check.lower() in joined for check in scenario.checks)
            results.append({'name':scenario.name,'passed':passed,'outputs':outputs})
        passed=sum(1 for r in results if r['passed'])
        return {'score':round(passed/len(results)*100,2),'passed':passed,'total':len(results),'results':results}
