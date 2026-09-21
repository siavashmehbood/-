# ایران — IRAN

IRAN یک runtime پژوهشی شناختی با پاسخ‌سازی محلی و نمادین، حافظهٔ SQLite، دانش قابل ردیابی و یادگیری با تأیید ناظر و انسان است. مدل پاسخ‌گو `iran` آفلاین است؛ **بازبینی آنلاین اختیاری** از چند Provider پشتیبانی می‌کند. این پروژه مدل زبانی عمومی یا سامانهٔ هوش عمومی تکمیل‌شده نیست.

## اجرا

Python 3.12 استفاده شده است. CLI به کتابخانهٔ استاندارد متکی است؛ برای GUI و تست‌ها:

```sh
python -m pip install -r requirements-dev.txt
python main.py
python gui.py
```

روی Windows نیز `python gui.py` همان `gui.ChatWindow` را اجرا می‌کند. برای هر پوشهٔ داده فقط **یک runtime** مجاز است؛ قفل سیستم‌عامل از بازشدن هم‌زمان runtime دوم جلوگیری می‌کند. `data/` شامل حافظه و صف پایدار است؛ آن را برای پاک‌سازی cache حذف نکنید. داده‌ها، logها، تنظیمات محلی و secretها در Git ثبت نمی‌شوند.

دستورهای مهم: `/internet off`، `/internet on`، `/learn pending`، `/learnweb <topic> [url ...]`، `/memory`، `/trace`، `/health` و `/exit`. رابط گرافیکی چت، وضعیت اینترنت و ناظرها، صف تأیید انسانی، آمار یادگیری، XP و trace را نشان می‌دهد.

## معماری واقعی

ورودی طبیعی از `IranRuntime.handle` به `CognitiveSystem` و `CognitivePipeline` می‌رود: context و reference resolution → Memory/Knowledge retrieval → Reasoning/Planning → پاسخ‌سازی → verification → تشخیص فرصت یادگیری. دستورهای CLI adapterهای runtime هستند. مسیرهای کوتاه محلی هم بررسی سازگاری پاسخ را اجرا می‌کنند؛ `PASS` این بررسی به معنی اثبات حقیقت بیرونی نیست.

- **Memory:** مکالمه، factهای صریح کاربر و درس‌ها در SQLite؛ نام اصلاح‌شده و سابقه حفظ می‌شوند. اطلاعات شخصیِ صریح کاربر فوراً قابل استفاده است و از دانش اینترنتی جداست.
- **Knowledge:** factهای محلی و bundleهای تأییدشده؛ منبع، زمان دریافت، ادعای مشترک و نتیجهٔ ناظر در bundle ذخیره می‌شود.
- **Learning:** یک LearningGate و یک صف بازبینی پایدار. ناظر فقط ارزیابی می‌کند؛ تولید پاسخ روزمره به آن وابسته نیست.
- **Effect Learning:** استفادهٔ واقعی از ادعای تأییدشده و نتایج قابل بررسی ثبت می‌شود؛ approval یا بازخورد مثبت به‌تنهایی XP نمی‌دهد. اعتبار اثرهای یکسان دوباره صادر نمی‌شود؛ هویت اعتبارهای نسخهٔ قدیمی نیز بدون دستکاری موجودی تاریخی مهاجرت می‌کند.
- **Curriculum:** هدف‌های مرحله‌ای و شکاف‌های دانش، با novelty/relevance و محدودیت تلاش. افزایش مرحله نیازمند assessment متمایز است؛ این معادل اثبات تسلط عمومی بر یک رشته نیست.

## مسیر یادگیری و بازبینی

Source Discovery → Retrieval → Extraction → Source Validation/Cross-check → Candidate → External Reviewer → Human Review → Learning Gate → Learning Engine → Effect Learning/Knowledge Update.

پیش از تأیید ناظر، محتوای candidate در صفحهٔ Human Review نمایش داده نمی‌شود. رد ناظر به رد candidate منتهی می‌شود. نبود ناظر، candidate را در `WAITING_FOR_REVIEWER` حفظ می‌کند. فعال‌شدن اینترنت و رسیدن نوبت پس از cooldown باعث تلاش دوباره می‌شود. تأیید هر مورد فقط همان مورد را اعمال می‌کند.

ثبت تأیید شامل checkpoint دانش/درس/اثر و backup حافظه است. در قطع اجرا پیش از ثبت نهایی، restart وضعیت قبل از اعمال را بازیابی می‌کند و candidate و بازبینی را نگه می‌دارد. خطای حین اعمال، ادامهٔ mutation را تا restart متوقف می‌کند. خرابی غیرقابل بازیابی در دفتر تأیید، تجربه یا XP با خطا اعلام می‌شود؛ این فایل‌ها بی‌صدا صفر نمی‌شوند.

## Providerها و تنظیمات

adapterهای `openrouter`، `gemini`، `groq` و `cerebras` از طریق `ProviderManager` استفاده می‌شوند. همه در تنظیمات پیش‌فرض غیرفعال‌اند. کلاس‌های قدیمی OpenRouter/Remote فقط facade سازگار با پاسخ‌گوی محلی و همین manager هستند؛ بخش قدیمی `openrouter` به‌تنهایی درخواست شبکه را فعال نمی‌کند. نام مدل، سقف‌ها و دسترسی رایگان باید با وضعیت جاری **حساب خودتان** بررسی شود؛ هیچ مدل یا سهمیه‌ای دائماً رایگان فرض نشده است.

`config.json` بخش `reviewers` دارد. فایل نادیده‌گرفته‌شدهٔ `reviewers.local.json` می‌تواند **محتوای همین بخش** را جایگزین کند؛ API key در آن هم ننویسید. از متغیر محیطی استفاده کنید:

| Provider | API key | انتخاب مدل |
| --- | --- | --- |
| OpenRouter | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL` |
| Groq | `GROQ_API_KEY` | `GROQ_MODEL` |
| Cerebras | `CEREBRAS_API_KEY` | `CEREBRAS_MODEL` |

برای فعال‌سازی، `enabled: true`، مدل دقیق و `free_policy` با `budget: 0`، `confirmed: true`، فهرست مدل‌های مجاز و `expires_at` آینده با timezone لازم است. تأیید محلی دسترسی رایگان ضمانت صورتحساب سرویس نیست؛ حساب فاقد دسترسی رایگان را فعال نکنید. تنظیمات پیش‌فرض هیچ سرویس پولی را فعال نمی‌کند.

هر Provider دارای timeout، retry، cooldown، health و failure reason است. fallback برای خرابی اتصال، rate limit، quota/model unavailable و پاسخ نامعتبر محدود است؛ **رد معتبر یک ادعا** باعث امتحان‌کردن ناظر بعدی برای گرفتن پاسخ دلخواه نمی‌شود. `AVAILABLE` یعنی شرایط محلی درخواست فراهم است، نه اینکه اتصال زنده قبلاً موفق بوده است. وضعیت‌ها و cooldown در restart حفظ می‌شوند.

مستندات رسمی برای بررسی شرایط حساب و مدل: [OpenRouter](https://openrouter.ai/docs/api_reference/limits)، [Gemini](https://ai.google.dev/gemini-api/docs/pricing)، [Groq](https://console.groq.com/docs/rate-limits)، [Cerebras](https://inference-docs.cerebras.ai/support/rate-limits).

## منابع دانش

فهرست `learning_sources` در `config.json` پیش‌فرض خالی است. فقط منابع منتخب را اضافه کنید. نمونهٔ ساختار (نشانی نمونه را با منبع واقعیِ بررسی‌شده عوض کنید):

```json
{
  "url": "https://docs.example.org/topic",
  "type": "documentation",
  "title": "Reference document",
  "topics": ["موضوع هدف"],
  "confidence": 0.7,
  "enabled": false
}
```

انواع `web`، `documentation`، `reference` و `structured_api` پشتیبانی می‌شوند. برای JSON از `text_path` مانند `data.description` استفاده کنید. Reviewer منبع دانش محسوب نمی‌شود. متن خام هرگز مستقیماً وارد Knowledge نمی‌شود. cross-check اختلاف عددی/نفی و استقلال تقریبی دامنه‌ها را بررسی می‌کند؛ fact-checker جامع نیست.

## اینترنت خاموش

حالت OFF پایدار است و مانع **شروع درخواست جدید** در مسیر learning/reviewer می‌شود. درخواستِ از قبل شروع‌شده ممکن است تا timeout ادامه یابد. چت محلی بدون key یا اینترنت کار می‌کند. کارهای شبکه، benchmark و ثبت تصمیم انسانی در GUI در worker اجرا می‌شوند. صف در restart باقی می‌ماند.

## تست و ارزیابی

```sh
python -m pytest -q
python -m unittest discover -s tests -q
python evaluation/runtime_suite.py
python evaluation/runtime_suite.py --repository /path/to/baseline
```

تست GUI با Qt offscreen واقعاً event loop را اجرا می‌کند. fixtureهای Provider پاسخ سرویس را شبیه‌سازی می‌کنند و آزمون سرویس زنده نیستند. نتایج و محدودیت‌های ممیزی در [گزارش ارزیابی](docs/runtime_validation.md) و [معماری](docs/runtime_architecture.md) آمده است. اجرای زندهٔ سرویس‌های بیرونی بدون key، quota و دسترسی حساب **BLOCKED** است.
