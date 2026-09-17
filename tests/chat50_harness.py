from runtime.app import IranRuntime

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

r = IranRuntime('.')
rows = []
for i, message in enumerate(MESSAGES, 1):
    answer = r.handle(message)
    rows.append((i, message, answer))
checks = {
    'name_recall': 'سیاوش' in rows[5][2],
    'project_identity': 'IRAN' in rows[6][2],
    'answer_reference': 'پایتخت ایران' in rows[9][2],
    'project_explanation': 'معماری شناختی' in rows[11][2],
    'goal_recall': 'فروش کتاب' in rows[23][2],
    'goal_correction': 'آموزش' in rows[25][2],
    'offline_constraint': 'آفلاین' in rows[28][2],
    'constraint_recall': 'آفلاین' in rows[30][2] and 'API' in rows[30][2],
    'previous_topic': 'کتاب' in rows[34][2],
    'project_list': 'دانا' in rows[48][2] and 'ایران' in rows[48][2],
    'active_topic': 'ایران' in rows[49][2],
}
score = sum(checks.values()) / len(checks)
with open('data/chat50_trace.txt', 'w', encoding='utf-8') as f:
    for i, message, answer in rows:
        f.write(f'TURN {i}\nUSER: {message}\nANSWER: {answer}\n\n')
    f.write('CHECKS\n')
    for name, passed in checks.items():
        f.write(f'{name}={passed}\n')
    f.write(f'score={score:.3f}\n')
r.close()
print(f'turns={len(rows)} score={score:.3f}')
for name, passed in checks.items():
    print(f'{name}={passed}')
if score < 0.90:
    raise SystemExit(1)
