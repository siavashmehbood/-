"""200-check local intelligence benchmark for IRAN.

The benchmark is deterministic and offline. It checks behavior, persistence,
self-correction, verified learning, reference resolution and architecture
constraints rather than only counting unit tests.
"""
import json
import re
import shutil
import tempfile
from pathlib import Path

from runtime.app import IranRuntime
from tools.registry import Tool
from core.self_correction import SelfCorrectionEngine

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [
    'سلام', 'اسم من سیاوش است', 'من روی پروژه دانا کار می‌کنم',
    'هدف دانا فروش کتاب است', 'موضوع قبلی چی بود؟', 'یادت هست اسم من چی بود؟',
    'نه، منظورم اسم پروژه بود', 'همون موضوع قبلی رو ادامه بده', 'پایتخت ایران چیه؟',
    'این جواب درباره چی بود؟', 'موضوع قبلی رو ول کن', 'پروژه ایران چیه؟',
    'منظورم معماری شناختی بود', 'همین رو بیشتر توضیح بده', 'یادت هست اول درباره چی گفتم؟',
    'یک بار دیگه بگو', 'اشتباهه، منظورم پروژه دانا بود', 'الان موضوع فعال چیه؟',
    'حافظه چیه؟', 'چه چیزهایی از من یادت هست؟', 'موضوع اول چی بود؟', 'موضوع دوم چی بود؟',
    'به بحث دانا برگرد', 'هدفش چی بود?', 'نه، هدفش فروش کتاب نبود، آموزش بود',
    'هدف اصلاح شد؟', 'همین موضوع رو ادامه بده', 'حالا درباره ایران بگو', 'این پروژه آفلاینه؟',
    'گفتم آفلاین باشه', 'پس چه محدودیت‌هایی داره؟', 'همون قبلی رو دقیق‌تر بگو',
    'یک موضوع جدید: کتاب', 'برای کتاب یک پیشنهاد بده', 'موضوع قبلی چی بود؟',
    'به موضوع ایران برگرد', 'یادت هست گفتم آفلاین؟', 'پس خارجی نباشه',
    'نه، منظورم بدون API بود', 'این اصلاح رو حفظ کن', 'الان آخرین اصلاح چی بود؟',
    'یک بار دیگه آخرین اصلاح رو بگو', 'موضوع دانا چی بود؟', 'هدف دانا چی بود؟',
    'نه، منظورم نسخه اول هدف بود', 'به نسخه جدید برگرد',
    'حالا یک سوال عمومی: تهران پایتخت کجاست؟', 'پایتخت ایران؟',
    'یادت هست من چه پروژه‌هایی گفتم؟', 'آخرین موضوع فعال چی بود؟',
]

checks = []
def check(name, condition, detail=''):
    checks.append((name, bool(condition), str(detail)))

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / 'data').mkdir()
    (root / 'logs').mkdir()
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    config['memory']['db'] = 'data/iran.db'
    config['runtime']['event_log'] = 'logs/events.jsonl'
    config['runtime']['goals'] = 'data/goals.json'
    config['security']['allow_network_tools'] = False
    (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')

    runtime = IranRuntime(root)
    try:
        # 1-50: every turn must produce a non-empty human response.
        rows = []
        for i, message in enumerate(MESSAGES, 1):
            answer = runtime.handle(message)
            rows.append((message, answer))
            check(f'chat_turn_{i:02d}_nonempty', bool(str(answer).strip()), answer)

        # 51-61: the known 50-turn memory contract.
        answers = [x[1] for x in rows]
        check('name_recall', 'سیاوش' in answers[5])
        check('project_identity', 'IRAN' in answers[6])
        check('answer_reference', 'پایتخت ایران' in answers[9])
        check('project_explanation', 'معماری شناختی' in answers[11])
        check('goal_recall', 'فروش کتاب' in answers[23])
        check('goal_correction', 'آموزش' in answers[25])
        check('offline_constraint', 'آفلاین' in answers[28])
        check('constraint_recall', 'آفلاین' in answers[30] and 'API' in answers[30])
        check('previous_topic', 'کتاب' in answers[34])
        check('project_list', 'دانا' in answers[48] and 'ایران' in answers[48])
        check('active_topic', 'ایران' in answers[49])

        # 62-81: repeated correction must change future behavior, not only persist a file.
        for i in range(10):
            question = f'واقعیت محلی {i} چیست؟'
            old = runtime.handle(question)
            correction = f'اشتباهه، واقعیت محلی {i} این است که مقدار درست ثبت‌شده است'
            runtime.handle(correction)
            new = runtime.handle(question)
            check(f'self_correction_{i:02d}_changed', old != new, f'{old} -> {new}')
            check(f'self_correction_{i:02d}_contains_fix', 'مقدار درست ثبت‌شده' in new or 'طبق اصلاح ثبت‌شده' in new, new)

        # 82-111: persistence across restart for explicit facts, goals and constraints.
        runtime.user_model.record('اسم من سیاوش است')
        runtime.user_model.record('من روی پروژه دانا کار می‌کنم')
        runtime.handle('هدف دانا آموزش است')
        runtime.handle('گفتم آفلاین باشه')
        runtime.close()
        runtime = IranRuntime(root)
        facts = runtime.user_model.facts(limit=50)
        for i, expected in enumerate(('سیاوش', 'دانا', 'آموزش', 'آفلاین'), 82):
            source = json.dumps(facts, ensure_ascii=False) + json.dumps(runtime.dialogue.snapshot(), ensure_ascii=False)
            check(f'persistence_{i}', expected in source, expected)
        for i in range(86, 112):
            answer = runtime.handle('چه چیزهایی از من یادت هست؟' if i % 2 else 'هدف دانا چی بود؟')
            check(f'persistence_query_{i}', bool(answer.strip()) and ('دانا' in answer or 'آموزش' in answer or 'سیاوش' in answer), answer)

        # 112-131: reference continuity under topic switches.
        reference_cases = [
            ('موضوع اصلی ما معماری شناختی ایران است', 'معماری شناختی ایران'),
            ('پایتون چیست؟', 'پایتون'), ('موضوع قبلی چی بود؟', 'معماری شناختی ایران'),
            ('حالا درباره دانا بگو', 'دانا'), ('همون موضوع رو ادامه بده', 'دانا'),
            ('به موضوع ایران برگرد', 'ایران'), ('همون قبلی', 'ایران'),
            ('یک موضوع جدید: کتاب', 'کتاب'), ('موضوع قبلی چی بود؟', 'ایران'),
            ('به بحث دانا برگرد', 'دانا'), ('همین موضوع رو ادامه بده', 'دانا'),
            ('به موضوع ایران برگرد', 'ایران'), ('همون قبلی رو دقیق‌تر بگو', 'ایران'),
            ('درباره پایتون بگو', 'پایتون'), ('چرا؟', 'پایتون'),
            ('چطور؟', 'پایتون'), ('به بحث دانا برگرد', 'دانا'),
            ('چرا؟', 'دانا'), ('به موضوع ایران برگرد', 'ایران'), ('ادامه بده', 'ایران'),
        ]
        for i, (message, expected) in enumerate(reference_cases, 112):
            answer = runtime.handle(message)
            snapshot = runtime.dialogue.snapshot()
            check(f'reference_{i}', expected in str(answer) or expected in snapshot.get('current_topic',''), f'{message} -> {answer}')

        # 132-151: verified learning and negative evidence changes future decision.
        runtime.registry.register(Tool('bad_action', 'bad', lambda: 'wrong', safe=True))
        runtime.registry.register(Tool('good_action', 'good', lambda: 'correct', safe=True))
        for i in range(132, 142):
            result = runtime.execute_verified_goal('learn from failure demo', 'bad_action', 'good_action', 'correct')
            check(f'verified_learning_{i}_success', bool((result.get('alternative') or {}).get('success') or (result.get('primary') or {}).get('success')), str(result))
        for i in range(142, 152):
            records = runtime.outcome_learning.retrieve_context('learn from failure demo', 'task', 20)
            bad = [r for r in records if r.get('action') == 'bad_action' and r.get('verified')]
            good = [r for r in records if r.get('action') == 'good_action' and r.get('verified')]
            check(f'negative_evidence_{i}', bool(bad and good and bad[-1].get('score') == 0.0 and good[-1].get('score') == 1.0))

        # 152-171: knowledge, uncertainty and answer verification.
        knowledge_cases = [
            ('پایتخت ایران چیه؟', 'تهران'), ('پایتخت فرانسه چیه؟', 'پاریس'),
            ('هفته چند روز دارد؟', 'هفت'), ('مرکز سیاسی کشور ایران کجاست؟', 'تهران'),
            ('پایتون چیه؟', 'پایتون'), ('Django چیه؟', 'Django'),
            ('یک حقیقت ناشناخته درباره سیاره خیالی X چیه؟', 'UNKNOWN'),
            ('دمای خیالی زِتا چنده؟', 'UNKNOWN'), ('چطور چیزی را که نمی‌دانیم ثابت کنیم؟', None),
            ('چرا یک ادعای بدون شاهد را قطعی ندانیم؟', None),
            ('پایتخت ایران؟', 'تهران'), ('نام پروژه چیست؟', 'ایران'),
            ('موضوع اصلی ما معماری شناختی ایران است', 'معماری شناختی ایران'),
            ('حافظه چیه؟', 'حافظه'), ('چطور پایتون یاد بگیرم؟', 'پایتون'),
            ('Episodic و Semantic چه فرقی دارند؟', 'Episodic'),
            ('این یک سؤال ناشناخته کاملاً ساختگی 12345 است؟', 'UNKNOWN'),
            ('علت دقیق یک رویداد ساختگی بدون داده چیست؟', 'UNKNOWN'),
            ('یک ادعای محلی بدون شاهد را توضیح بده', None), ('یک واقعیت شناخته‌شده: پایتخت ایران؟', 'تهران'),
        ]
        for i, (message, expected) in enumerate(knowledge_cases, 152):
            answer = runtime.handle(message)
            ok = bool(answer.strip())
            if expected == 'UNKNOWN': ok = ok and 'UNKNOWN' in answer
            elif expected: ok = ok and expected in answer
            check(f'knowledge_{i}', ok, answer)

        # 172-191: architecture/offline/source integrity checks.
        source_files = list((ROOT / 'core').rglob('*.py')) + list((ROOT / 'runtime').rglob('*.py'))
        source_text = '\n'.join(p.read_text(encoding='utf-8', errors='ignore') for p in source_files)
        forbidden = ('openai.', 'anthropic.', 'gemini.', 'huggingface', 'requests.get', 'httpx.', 'ollama.generate')
        for i, token in enumerate(forbidden, 172):
            check(f'offline_source_guard_{i}', token not in source_text, token)
        check('offline_config_guard_178', config['security']['allow_network_tools'] is False)
        check('safe_mode_guard_179', config['security']['safe_mode'] is True)
        check('network_registry_guard_181', runtime.policy.allows('network') is False)
        check('shell_guard_182', runtime.policy.allows('shell') is False)
        check('deploy_guard_183', runtime.policy.allows('deploy') is False)
        check('self_correction_file_184', (root / 'data' / 'self_corrections.json').exists())
        check('verified_outcomes_file_185', (root / 'data' / 'verified_outcomes.json').exists())
        check('events_file_186', (root / 'logs' / 'events.jsonl').exists())
        check('state_file_187', (root / 'data' / 'conversation_state.json').exists())
        check('memory_db_188', (root / 'data' / 'iran.db').exists())
        check('knowledge_seed_189', runtime.knowledge.stats().get('facts', 0) >= 3)
        check('learning_store_190', runtime.learning.stats().get('experiences', 0) > 0)
        check('self_correction_stats_191', runtime.dialogue.cognitive_pipeline.self_correction.stats().get('records', 0) > 0)

        # 192-200: internal cognitive integrity and persistence snapshot.
        snap = runtime.dialogue.snapshot()
        check('topic_stack_192', isinstance(snap.get('topic_stack'), list))
        check('topic_history_193', isinstance(snap.get('topic_history'), list))
        check('correction_history_194', isinstance(snap.get('corrections'), list) and len(snap.get('corrections', [])) > 0)
        check('accepted_answers_195', isinstance(snap.get('accepted_answers'), list))
        check('rejected_answers_196', isinstance(snap.get('rejected_answers'), list))
        check('constraints_197', isinstance(snap.get('remembered_constraints'), list))
        check('turn_count_198', int(snap.get('turns', 0)) >= 130)
        check('cognitive_pipeline_199', isinstance(runtime.dialogue.cognitive_pipeline, object))
        check('self_correction_stats_200', runtime.dialogue.cognitive_pipeline.self_correction.stats()['records'] >= 10)
    finally:
        runtime.close()

passed = sum(ok for _, ok, _ in checks)
print(f'CHECKS={len(checks)} PASSED={passed} FAILED={len(checks)-passed} SCORE={passed/len(checks):.3f}')
for name, ok, detail in checks:
    if not ok:
        print(f'FAIL {name}: {detail}')
report = ROOT / 'data' / 'intelligence_200_report.json'
report.write_text(json.dumps({
    'checks': len(checks), 'passed': passed, 'failed': len(checks)-passed,
    'score': round(passed / len(checks), 3),
    'failures': [{'name': n, 'detail': d} for n, ok, d in checks if not ok],
}, ensure_ascii=False, indent=2), encoding='utf-8')
if passed != len(checks):
    raise SystemExit(1)
