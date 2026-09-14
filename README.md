# ایران — Personal General Intelligence Research Platform

نسخه فعلی: **0.28.0**

ایران یک هسته شخصی برای ساخت یک سیستم هوشمند عمومی‌گراست؛ معماری آن از چت، حافظه، برنامه‌ریزی، ابزار، ارزیابی، امنیت و sandbox تشکیل شده است.

## وضعیت فعلی
- Agent + Brain + Provider مستقل
- Provider محلی `iran-local` بدون وابستگی به Ollama
- Structured Persian Language Intelligence با حفظ raw_text و normalized_text
- تشخیص چند intent، constraint، negation، temporal، reference و ambiguity
- Provider اختیاری OpenAI-compatible برای اتصال مدل زبانی واقعی
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
- `/tools` ابزارها و permissionها
- `/tool NAME key=value` اجرای ابزار
- `/evaluate` بررسی کد
- `/sandbox` ساخت snapshot و ارزیابی
- `/events` رویدادهای اخیر
- `/help` راهنما
- `/exit` خروج

## اتصال مدل زبانی واقعی
Provider فعلی عمداً محلی و سبک است تا پروژه بدون مدل خارجی بالا بیاید. برای فعال‌کردن یک مدل واقعی، `model.provider` را روی `openai-compatible` بگذارید و متغیرهای محیطی `IRAN_MODEL_API_KEY`، `IRAN_MODEL_ENDPOINT` و در صورت نیاز `IRAN_MODEL_NAME` را تنظیم کنید.

## امنیت
Safe Mode فعال است. Shell، write و deploy خودکار بسته‌اند. دسترسی شبکه فقط از permission جداگانه `network` عبور می‌کند. هیچ قابلیت خودبهسازی حق ندارد مستقیماً production را تغییر دهد.

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
