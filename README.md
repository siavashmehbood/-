# ایران — Personal General Intelligence Research Platform

نسخه فعلی: **0.28.0**

ایران یک هسته شخصی برای ساخت یک سیستم هوشمند عمومی‌گراست؛ معماری آن از چت، حافظه، برنامه‌ریزی، ابزار، ارزیابی، امنیت و sandbox تشکیل شده است.

**ایران کاملاً آفلاین و نمادین است.** این پروژه از OpenAI، ChatGPT، Ollama، Llama، Qwen، Mistral، مدل pretrained، embedding service یا API هوش مصنوعی خارجی استفاده نمی‌کند. درک زبان، حافظه، استدلال، برنامه‌ریزی و تولید پاسخ با قواعد محلی، دانش گرافی، شواهد، حافظه و پاسخ‌سازی ترکیبی خود پروژه انجام می‌شود.

## وضعیت فعلی
- Agent + Brain + Provider مستقل
- Provider محلی `iran-local` بدون وابستگی به Ollama
- Structured Persian Language Intelligence با حفظ raw_text و normalized_text
- تشخیص چند intent، constraint، negation، temporal، reference و ambiguity
- حافظه پایدار SQLite با جستجو و آمار
- Planning تطبیقی و Goal Store
- Tool Registry با permissionهای read/write/network
- ابزارهای زمان، حافظه، فایل پروژه، مشخصات سیستم، خلاصه پروژه و web fetch
- Event log و health check
- Self Model و Evaluator
- Snapshot/Sandbox برای تغییرات آزمایشی
- Safe Mode و approval gate برای عملیات پرخطر
- GUI پایدار با worker thread + queue و ثبت خطا

## معماری
`GUI/CLI -> Orchestrator -> Agent -> Brain -> Provider`

`Orchestrator -> Planner + Memory + Goals + Tool Registry + Security + Events`

`Evaluator + Sandbox -> تست و آماده‌سازی نسخه‌های بعدی`

## اجرای پروژه
از پوشه پروژه:

`python main.py`

برای رابط گرافیکی، میانبر دسکتاپ **Iran AI** یا `iran_gui.pyw` را اجرا کنید.

## دستورات CLI
- `/status` وضعیت کامل
- `/health` سلامت سیستم
- `/self` مدل و محدودیت‌های ایران
- `/model` وضعیت Provider
- `/memory` حافظه اخیر
- `/goals` هدف‌ها
- `/goal TITLE` ساخت هدف
- `/goal-done ID` تکمیل هدف
- `/plan` ساخت برنامه
- `/reason TEXT` تحلیل هدف
- `/run GOAL --tool NAME --expected VALUE [--alternative NAME] [--arg key=value]` اجرای task با مشاهده، verification و replanning واقعی
- `/tools` ابزارها و permissionها
- `/tool NAME key=value` اجرای ابزار
- `/evaluate` بررسی کد
- `/sandbox` ساخت snapshot و ارزیابی
- `/events` رویدادهای اخیر
- `/help` راهنما
- `/exit` خروج

## پاسخ‌سازی نمادین و آفلاین
Provider رسمی پروژه `iran` و حالت آن `offline-symbolic` است. پاسخ مستقیم factual، پاسخ ناشناخته با برچسب `UNKNOWN`، توضیح why/how، مقایسه، بازیابی حافظه و ارجاع مکالمه‌ای بدون مدل زبانی آماده تولید می‌شوند. تحلیل داخلی در state و event log باقی می‌ماند و نباید مستقیماً به‌عنوان پاسخ کاربر نمایش داده شود.

اگر دانش محلی برای یک پرسش وجود نداشته باشد، ایران حدس را واقعیت اعلام نمی‌کند و `UNKNOWN` برمی‌گرداند.

## ارزیابی و benchmark محلی
برای مشاهده کیفیت آخرین پاسخ در CLI از `/quality` و برای اجرای benchmark فارسی از `/benchmark` استفاده کنید. benchmark شامل پاسخ factual، `UNKNOWN`، clarification، reference resolution، why، how، comparison و feedback است. دستور `/trace` eventهای چرخه شناختی را به‌شکل خوانا نشان می‌دهد و `/knowledge QUERY` دانش محلی را جست‌وجو می‌کند.

یادگیری procedural فقط strategy، confidence و ranking را تغییر می‌دهد و source code، permission یا سیاست امنیتی را به‌صورت خودکار تغییر نمی‌دهد.

هر event شناختی اکنون `turn_id`، `stage`، `status` و `duration_ms` دارد تا چرخه هر درخواست از ادراک تا پاسخ، ارزیابی و یادگیری قابل ردیابی باشد. eventهای راه‌اندازی با شناسه `system` جدا می‌شوند و با trace یک turn کاربر مخلوط نمی‌شوند.

## امنیت
Safe Mode فعال است. Shell، write و deploy خودکار بسته‌اند. دسترسی شبکه فقط از permission جداگانه `network` عبور می‌کند. هیچ قابلیت خودبهسازی حق ندارد مستقیماً production را تغییر دهد.

## Verified Task Execution
برای اجرای یک هدف به‌عنوان task قابل‌اعتبارسنجی، باید ابزار و اثر مورد انتظار صریحاً اعلام شوند. موفقیت فقط وقتی ثبت می‌شود که خروجی مشاهده‌شده با `expected` تطبیق داشته باشد؛ پاسخ متنی به‌تنهایی مدرک موفقیت نیست. در صورت شکست، با افزودن `--alternative`، runtime مسیر را به ابزار جایگزین replan می‌کند.

نمونه:

`/run verify demo --tool primary_tool --expected "correct result" --alternative fallback_tool`

پارامترهای ابزار با `--arg key=value` ارسال می‌شوند. ابزار همچنان از permissionهای Safe Mode عبور می‌کند و رویدادهای plan، action، observation، verification و replanning در event log ثبت می‌شوند.

## مسیر بعدی
1. اتصال مدل زبانی واقعی
2. Tool-calling استاندارد و schema validation
3. حافظه معنایی/vector retrieval
4. Vision
5. Voice
6. Browser automation محدود و امن
7. Self-healing با diagnostics و rollback
8. Controlled self-improvement با benchmark
9. Phone interface
10. Multi-agent orchestration

## اصل پروژه
`Understand -> Plan -> Act -> Observe -> Evaluate -> Remember -> Repair -> Improve`

هدف، ساخت یک سیستم قابل‌فهم، تست‌پذیر، برگشت‌پذیر و قابل ارتقاست؛ نه ادعای خودآگاهی واقعی.

## Intelligence Engine 0.10
- Fast intent classification before model/tool execution
- Confidence-aware decisions and explainable action selection
- Working-memory retrieval combining semantic-like keyword matches with recency
- Runtime metrics for latency, tool usage, retries and responses
- Bounded agent loop with lightweight result scoring
- Integrated scheduler/background runner
- Evaluator attached to runtime and sandbox remains approval-gated

## Structured Persian Intelligence 0.28
- Raw input is preserved alongside normalized text.
- Structured semantic representation enters runtime telemetry.
- Multi-intent, constraints, negation, temporal expressions and references are benchmarked.
- Compound repair/test requests are represented as explicit action intents.
- Boundary-safe reference detection avoids matching «این» inside words such as «اینترنت».


## Task C — Memory Graph, Procedural Memory, Skills & Transfer

Version 0.29.0 adds a structured learning-transfer layer while reusing the existing KnowledgeGraph and LearningEngine.

- `knowledge/knowledge_graph.py`: typed nodes, typed edges, provenance-aware graph relations, contradiction retention and multi-hop graph queries.
- `learning/procedural_memory.py`: persistent structured procedures with preconditions, verification/failure conditions and outcome updates.
- `learning/skill_system.py`: persistent discover/retrieve/apply/verify/update/disable skill lifecycle over procedural memory.
- `learning/learning_engine.py`: outcome-backed `transfer_real`; transfer success requires verified positive improvement over baseline.
- `self/task_c_benchmark.py`: deterministic benchmark with 20 nodes, 30 edges, 10 procedures, 10 skills and 10 transfer pairs.
- `runtime/app.py`: Task C components are integrated into runtime and cognitive-cycle skill retrieval telemetry.

Task C safety remains local and policy-gated: `safe_mode=true`, `allow_shell=false`, `auto_deploy=false`.
