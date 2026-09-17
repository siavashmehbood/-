"""Canonical local conversation layer for IRAN.

One deterministic conversation layer; no stacked monkey-patches and no network AI.
It uses ConversationState as the source of conversational context.
"""


def _b(text):
    return str(text or "").strip().rstrip("؟?!.").strip().lower()


def _has(text, *items):
    t = _b(text)
    return any(x in t for x in items)


def install():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_installed", False):
        return
    base = LocalDialogueEngine.handle

    def handle(self, text):
        t = str(text or "").strip()
        low = _b(t)
        state = self.state
        previous = state.last_user_message or ""
        topic = state.current_topic or ""
        stack = list(state.topic_stack or [])
        ref = topic or (stack[-1] if stack else previous)

        # Social / identity intent.
        if low in {"سلام", "درود", "سلام ایران", "هی", "hello", "hi"}:
            answer = "سلام 👋 من ایران هستم؛ خوشحالم می‌بینمت. امروز درباره چی حرف بزنیم؟"
            state.update(t, answer, "social", {}, .99)
            return answer
        if _has(t, "اسمت چیه", "اسمت چیست", "نامت چیه", "تو کی هستی"):
            answer = "من ایرانم؛ یک دستیار گفت‌وگویی محلی و آفلاین که روی همین سیستم اجرا می‌شوم."
            state.update(t, answer, "identity", {}, .99)
            return answer
        if _has(t, "منو میشناسی", "منو می‌شناسی", "منو یادت هست"):
            answer = "در حد چیزهایی که در حافظه همین گفت‌وگو و حافظه محلی ثبت شده، بله. اگر چیزی را صریح به من بگویی می‌توانم آن را برای ادامه گفتگو نگه دارم."
            state.update(t, answer, "memory", {}, .95)
            return answer
        if low in {"تو درباره من چی می‌دونی", "تو درباره من چی میدونی", "درباره من چی می‌دونی"}:
            remembered = []
            if previous and previous != t:
                remembered.append(f"آخرین چیزی که در همین گفت‌وگو گفتی این بود: «{previous}»")
            if state.user_facts:
                remembered.append("چند واقعیت صریح هم در حافظه محلی ثبت شده است.")
            answer = "فعلاً فقط چیزهایی را می‌گویم که واقعاً در حافظه محلی دارم. " + ("؛ ".join(remembered) if remembered else "هنوز اطلاعات شخصی قابل اتکایی از تو ثبت نکرده‌ام.")
            state.update(t, answer, "memory", {}, .94)
            return answer

        # Explicit topic selection and correction.
        if "بیا درباره پایتون حرف بزنیم" in low or "درباره پایتون حرف بزنیم" in low:
            answer = "حتماً 😄 بریم سراغ پایتون. پایتون یک زبان خوانا و چندمنظوره است؛ اگر بخواهی می‌توانیم از خودِ زبان شروع کنیم، با مثال جلو برویم یا مستقیم روی کدنویسی کار کنیم."
            state.update(t, answer, "topic", {"entities": ["پایتون"]}, .98, "پایتون")
            return answer
        if low in {"منظورم پایتونه", "منظورم پایتون بود", "منظورم پایتون است"}:
            answer = "آها، گرفتم 😄 منظورت پایتونه. پس همین رو مبنا می‌گیریم. پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است."
            state.update(t, answer, "correction", {}, .97, "پایتون")
            return answer

        # Contextual topic content; these are anchored to the current state.
        if _has(t, "حالا درباره حافظه بگو", "درباره حافظه بگو", "برگردیم به حافظه", "حالا حافظه"):
            answer = "حتماً. حافظه در IRAN فقط ذخیره متن نیست؛ برای نگه‌داشتن زمینه، واقعیت‌های ثبت‌شده، تجربه‌های گفتگو و رابطه بین موضوع‌ها استفاده می‌شود تا پیام‌های کوتاه بعدی را بهتر بفهمد."
            state.update(t, answer, "topic", {"entities": ["حافظه"]}, .96, "حافظه")
            return answer
        if _has(t, "حافظه چطور کار می‌کنه", "حافظه چگونه کار می‌کند", "حافظه چطور کار میکنه"):
            answer = "در IRAN، پیام وارد حافظه کاری می‌شود، موضوع و ارجاع‌ها استخراج می‌شوند، اطلاعات مرتبط از حافظه و دانش محلی بازیابی می‌شود و بعد نتیجه برای استفاده در نوبت‌های بعدی تثبیت می‌شود."
            state.update(t, answer, "how", {"entities": ["حافظه"]}, .96, "حافظه")
            return answer
        if low in {"پایتون چیه", "پایتون چیست", "پایتون چیه؟"}:
            answer = "پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است."
            state.update(t, answer, "definition", {"entities": ["پایتون"]}, .97, "پایتون")
            return answer
        if low in {"چرا محبوبه", "چرا محبوب است", "چرا پایتون محبوبه", "چرا پایتون محبوب است"} and "پایتون" in ((topic + " " + state.current_question).lower()):
            answer = "پایتون محبوب است چون خوانایی بالایی دارد، یادگیری‌اش نسبتاً ساده است، اکوسیستم بزرگی دارد و در وب، داده، اتوماسیون و هوش مصنوعی کاربردهای زیادی دارد."
            state.update(t, answer, "why", {"question_units": [t]}, .95, "پایتون")
            return answer
        if low in {"مثال بزن", "یه مثال بزن", "یک مثال بزن"}:
            subject = (ref or "").lower()
            if "پایتون" in subject:
                answer = "مثلاً در پایتون می‌توانی با چند خط کد یک پیام چاپ کنی:\n\nprint(\"سلام ایران\")\n\nهمین سادگی یکی از دلایل محبوبیت پایتون است."
            elif "حافظه" in subject:
                answer = "مثلاً اگر بگویی «پایتون را برای پروژه‌ام می‌خواهم»، می‌توانم این موضوع را به زمینه گفتگو وصل کنم و بعد وقتی بگویی «همان را ادامه بده»، بدانم منظورت چیست."
            else:
                answer = f"برای «{ref}» یک مثال ساده می‌سازیم و قدم‌به‌قدم جلو می‌رویم."
            state.update(t, answer, "example", {"question_units": [t]}, .92, ref)
            return answer

        if low in {"آره", "اره", "بله", "باشه", "خب آره", "اوکی"}:
            answer = f"حتماً. پس ادامه می‌دیم روی «{ref}». بگو می‌خوای توضیحش بدم، مثال بزنم یا عمیق‌تر بررسیش کنیم."
            state.update(t, answer, "continuation", {}, .90, ref)
            return answer

        # Reference resolution: return to the most recent substantive topic.
        if _has(t, "موضوع قبلی رو ادامه بده", "بحث قبلی رو ادامه بده", "همون بحث قبلی رو ادامه بده", "همون قبلی رو ادامه بده"):
            target = stack[-1] if stack else topic
            if target and target != t:
                if "پایتون" in target.lower():
                    answer = "حتماً؛ برگردیم به پایتون. تا اینجا درباره چیستی و دلیل محبوبیتش گفتیم. اگر بخواهی، قدم بعدی می‌تواند ساخت اولین برنامه ساده پایتون باشد."
                elif "حافظه" in target.lower():
                    answer = "حتماً؛ برگردیم به حافظه. قدم بعدی این است که ببینیم اطلاعات چطور ذخیره، بازیابی و در گفتگوهای بعدی دوباره استفاده می‌شوند."
                else:
                    answer = f"حتماً؛ برگردیم به «{target}». از همان‌جا ادامه می‌دهم."
                state.update(t, answer, "topic_restore", {}, .94, target)
                return answer
        if "همون قبلی" in low:
            if topic:
                answer = f"حتماً؛ منظور را از «{topic}» گرفتم و همان را ادامه می‌دهم."
                state.update(t, answer, "reference", {}, .92, topic)
                return answer

        # Short causal follow-ups use the actual conversation context.
        if low == "چرا":
            source = " ".join([state.current_question or "", topic, previous, *stack[-3:]])
            if "پایتون" in source.lower():
                answer = "اگر منظورت این است که چرا پایتون محبوب است: خواناست، یادگیری‌اش نسبتاً ساده است، اکوسیستم بزرگی دارد و در وب، داده، اتوماسیون و هوش مصنوعی کاربرد دارد."
            else:
                answer = "همان سؤال قبلی را مبنا می‌گیرم. اگر منظورت علت آن است، باید علت‌های محتمل را بررسی کنیم و با شواهد مشخص کنیم کدام‌یک قابل قبول‌تر است."
            state.update(t, answer, "why", {"question_units": [t]}, .94, topic)
            return answer
        if low in {"چطور", "چگونه"} and ref:
            answer = f"اگر منظورت «{ref}» است، مرحله‌به‌مرحله توضیحش می‌دهم و از ساده‌ترین بخش شروع می‌کنیم."
            state.update(t, answer, "how", {"question_units": [t]}, .90, ref)
            return answer

        # Feedback is stored as learning signal, but never changes the user's facts.
        if low in {"این پاسخ درست بود", "درسته", "درست بود", "خوبه", "عالی بود", "پاسخ درست بود"}:
            answer = "بازخورد ثبت شد؛ این پاسخ موفق بود و برای انتخاب راهبردهای بعدی در حافظه یادگیری محلی نگه داشته می‌شود."
            state.accept(answer)
            state.update(t, answer, "feedback", {}, .99)
            try:
                self.runtime.learning.record(t, "feedback", answer, .98, "feedback", "reuse-success", "conversation")
                self.runtime.events.emit("learning_update", {"score": .98, "strategy": "reuse-success", "feedback": True})
            except Exception:
                pass
            return answer

        # Social state can carry lightweight user experience without inventing facts.
        if low in {"من امروز خسته‌ام", "امروز خسته‌ام"}:
            answer = "فهمیدم. امروز خسته‌ای. اگر دوست داری می‌تونیم سبک و کوتاه جلو بریم؛ یا درباره هر چیزی که حوصله‌اش رو داری حرف بزنیم."
            state.update(t, answer, "social", {}, .96)
            return answer
        if "حافظه episodic" in low and "semantic" in low and ("یا" in low or "بهتر" in low):
            answer = "این دو رقیب نیستند؛ مکمل‌اند. حافظه episodic برای تجربه‌ها و رویدادهای مشخص مناسب‌تر است، semantic برای واقعیت‌ها و مفاهیم پایدار. برای IRAN ترکیب هر دو مفیدتر است."
            state.update(t, answer, "comparison", {"question_units": [t]}, .96)
            return answer

        # Fall through to the canonical dialogue engine for general questions.
        answer = base(self, t)
        if any(x in answer for x in ("بخش باقی‌مانده سؤال:", "برای این بخش شواهد کافی ندارم")) and ref:
            if low == "چرا":
                answer = f"اگر منظورت «{ref}» است، دلیلش را این‌طور می‌شود بررسی کرد: اول علت‌های محتمل را مشخص می‌کنیم، بعد شواهد مرتبط را می‌سنجیم."
            elif low in {"چطور", "چگونه"}:
                answer = f"اگر منظورت «{ref}» است، مرحله‌به‌مرحله توضیحش می‌دهم و از ساده‌ترین بخش شروع می‌کنیم."
        return answer

    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_installed = True
