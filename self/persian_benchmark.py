from statistics import mean

class PersianLanguageBenchmark:
    """Runtime benchmark for structured Persian understanding, not response templates."""
    def run(self, intelligence):
        checks = []
        cases = [
            ('build', 'يک ابزار امن بساز'), ('debug', 'چرا برنامه خطا می‌دهد؟'),
            ('inspection', 'وضعیت پروژه را بررسی کن'), ('planning', 'برای این کار برنامه‌ریزی کن'),
            ('memory', 'یادت هست قبلاً چه گفتیم؟'), ('compare', 'این بهتره یا قبلی؟'),
            ('negation', 'این را نساز و بدون اینترنت کار کن'),
            ('temporal', 'فردا نسخه قبلی را بررسی کن'),
            ('reference', 'همونو با تست کامل انجام بده'),
            ('mixed', 'Python رو بررسی کن و بعد test بگیر'),
            ('multi', 'بررسی کن، اگر مشکل داشت درستش کن و تست بگیر'),
            ('constraint', 'فقط این فایل را تغییر بده و با تست کامل'),
        ]
        for kind, text in cases:
            x = intelligence.analyze(text, {'topic':'پروژه','goal':'ساخت سیستم'})
            if kind in {'build','debug','inspection','planning','memory','compare'}:
                checks.append(float(x['intent'] == kind))
            elif kind == 'negation':
                checks.append(float(x['negations'] and any('بدون' in c for c in x['constraints'])))
            elif kind == 'temporal':
                checks.append(float('فردا' in x['temporal'] and 'قبلی' in x['references']))
            elif kind == 'reference':
                checks.append(float('همونو' in x['references'] or 'همون' in x['references']))
            elif kind == 'mixed':
                checks.append(float(x['language'] == 'mixed'))
            elif kind == 'multi':
                checks.append(float(x['multi_intent'] and len(x['intents']) >= 2))
            elif kind == 'constraint':
                checks.append(float(any('فقط' in c for c in x['constraints']) and any('تست' in c for c in x['constraints'])))
        return {'cases': len(checks), 'score': round(mean(checks), 3), 'passed': mean(checks) >= .80}
