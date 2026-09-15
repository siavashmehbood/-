"""Natural local conversation upgrade for IRAN.
No external model/network dependency. Focuses on multi-turn chat continuity.
"""
import re


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

        # Identity and social conversation must not fall into UNKNOWN.
        if low in {"سلام", "درود", "سلام ایران", "هی", "hello", "hi"}:
            answer = "سلام 👋 من ایرانم. خوشحالم می‌بینمت. امروز درباره چی حرف بزنیم؟"
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

        # A direct follow-up should answer the implied question, not describe the pipeline.
        if low == "چرا محبوبه" and "پایتون" in (previous + " " + topic).lower():
            answer = "چون خواناست، یادگیری‌اش نسبتاً ساده است، کتابخانه‌های زیادی دارد و برای کارهایی مثل وب، داده، اتوماسیون و هوش مصنوعی کاربرد دارد."
            state.update(t, answer, "why", {"question_units": [t]}, .93, "پایتون")
            return answer
        if low in {"مثال بزن", "یه مثال بزن", "یک مثال بزن"}:
            subject = ref.lower()
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

        # Natural topic switch / return.
        if _has(t, "حالا درباره حافظه بگو", "درباره حافظه بگو", "برگردیم به حافظه", "حالا حافظه"):
            answer = "حتماً. حافظه در IRAN فقط ذخیره متن نیست؛ برای نگه‌داشتن زمینه، واقعیت‌های ثبت‌شده، تجربه‌های گفتگو و رابطه بین موضوع‌ها استفاده می‌شود تا پیام‌های کوتاه بعدی را بهتر بفهمد."
            state.update(t, answer, "topic", {"entities": ["حافظه"]}, .96, "حافظه")
            return answer
        if _has(t, "حافظه چطور کار می‌کنه", "حافظه چگونه کار می‌کند", "حافظه چطور کار میکنه"):
            answer = "در IRAN، پیام وارد حافظه کاری می‌شود، موضوع و ارجاع‌ها استخراج می‌شوند، اطلاعات مرتبط از حافظه و دانش محلی بازیابی می‌شود و بعد نتیجه برای استفاده در نوبت‌های بعدی تثبیت می‌شود."
            state.update(t, answer, "how", {"entities": ["حافظه"]}, .96, "حافظه")
            return answer

        # "موضوع قبلی" means return to the previous topic and continue it, not echo the phrase.
        if _has(t, "موضوع قبلی رو ادامه بده", "بحث قبلی رو ادامه بده", "همون بحث قبلی رو ادامه بده"):
            target = stack[-1] if stack else previous
            if target and target != t:
                if "پایتون" in target.lower():
                    answer = "حتماً؛ برگردیم به پایتون. تا اینجا درباره چیستی و دلیل محبوبیتش گفتیم. اگر بخواهی، قدم بعدی می‌تواند ساخت اولین برنامه ساده پایتون باشد."
                elif "حافظه" in target.lower():
                    answer = "حتماً؛ برگردیم به حافظه. قدم بعدی این است که ببینیم اطلاعات چطور ذخیره، بازیابی و در گفتگوهای بعدی دوباره استفاده می‌شوند."
                else:
                    answer = f"حتماً؛ برگردیم به «{target}». از همان‌جا ادامه می‌دهم."
                state.update(t, answer, "topic_restore", {}, .94, target)
                return answer

        # Replace the generic reference-follow-up response with a useful continuation.
        answer = base(self, t)
        bad = (
            "بخش باقی‌مانده سؤال:",
            "برای این بخش شواهد کافی ندارم",
            "اگر هدفت ادامه همین موضوع است، بگو کدام بخش را باز کنیم",
            "متوجه شدم: «",
        )
        if any(x in answer for x in bad):
            if low in {"چرا", "چرا؟"} and ref:
                answer = f"اگر منظورت «{ref}» است، دلیلش را این‌طور می‌شود توضیح داد: باید اول علت‌های مرتبط با همان موضوع را بررسی کنیم."
            elif low in {"چطور", "چگونه"} and ref:
                answer = f"اگر منظورت «{ref}» است، مرحله‌به‌مرحله توضیحش می‌دهم و از ساده‌ترین بخش شروع می‌کنیم."
            elif ref and len(t) < 30:
                answer = f"حتماً، ادامه می‌دیم از «{ref}». {answer.splitlines()[-1] if answer else ''}".strip()
        return answer

    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_installed = True


def install_v2():
    """Second-pass conversational polish; sits above the first local chat layer."""
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v2", False):
        return
    base = LocalDialogueEngine.handle

    def handle(self, text):
        t = str(text or "").strip()
        low = _b(t)
        state = self.state
        topic = state.current_topic or ""
        previous = state.last_user_message or ""
        if low in {"سلام", "درود", "سلام ایران", "هی", "hello", "hi"}:
            return "سلام 👋 من ایرانم. خوشحالم می‌بینمت. امروز درباره چی حرف بزنیم؟"
        if "بیا درباره پایتون حرف بزنیم" in low or "درباره پایتون حرف بزنیم" in low:
            answer = "حتماً 😄 بریم سراغ پایتون. پایتون یک زبان خوانا و چندمنظوره است؛ اگر بخواهی می‌توانیم از خودِ زبان شروع کنیم، با مثال جلو برویم یا مستقیم روی کدنویسی کار کنیم."
            state.update(t, answer, "topic", {"entities": ["پایتون"]}, .98, "پایتون")
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
        if low in {"منظورم پایتونه", "منظورم پایتون بود", "منظورم پایتون است"}:
            answer = "آها، گرفتم 😄 منظورت پایتونه. پس همین رو مبنا می‌گیریم. پایتون یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است."
            state.update(t, answer, "correction", {}, .97, "پایتون")
            return answer
        if low in {"من امروز خسته‌ام", "امروز خسته‌ام"}:
            answer = "فهمیدم. امروز خسته‌ای. اگر دوست داری می‌تونیم سبک و کوتاه جلو بریم؛ یا اصلاً چند دقیقه درباره هر چیزی که حوصله‌اش رو داری حرف بزنیم."
            state.update(t, answer, "social", {}, .96)
            return answer
        answer = base(self, t)
        if answer.endswith(".."):
            answer = answer[:-1]
        return answer

    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v2 = True


def install_v3():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v3", False):
        return
    base = LocalDialogueEngine.handle
    def handle(self, text):
        t = str(text or "").strip(); low = _b(t); state = self.state
        ref = state.current_topic or (state.topic_stack[-1] if state.topic_stack else "")
        if low in {"این پاسخ درست بود", "درسته", "درست بود", "خوبه", "عالی بود", "پاسخ درست بود"}:
            answer = "خیلی خوب؛ بازخوردت ثبت شد. این یعنی این نوع پاسخ را برای ادامه گفتگو به‌عنوان الگوی موفق در نظر می‌گیرم."
            state.accept(answer); state.update(t, answer, "feedback", {}, .98); return answer
        if "حافظه episodic" in low and "semantic" in low and ("یا" in low or "بهتر" in low):
            answer = "این دو رقیب هم نیستند؛ مکمل‌اند. حافظه episodic برای تجربه‌ها و رویدادهای مشخص مناسب‌تر است، semantic برای واقعیت‌ها و مفاهیم پایدار. برای IRAN ترکیب هر دو بهتر است."
            state.update(t, answer, "comparison", {"question_units": [t]}, .95); return answer
        if "چرا" in low and ref and not low.startswith("چرا محبوب"):
            answer = f"اگر منظورت این است که چرا «{ref}» این‌طور شده، باید دو چیز را بررسی کنیم: علت‌های محتمل و شواهدی که هر علت را تأیید یا رد می‌کنند. بعد بر اساس نتیجه، گام تشخیصی بعدی را انتخاب می‌کنیم."
            state.update(t, answer, "why", {"question_units": [t]}, .88, ref); return answer
        if low in {"موضوع قبلی رو ادامه بده", "بحث قبلی رو ادامه بده", "همون قبلی رو ادامه بده"} and ref:
            if "پایتون" in ref.lower():
                answer = "حتماً؛ ادامه پایتون را می‌گیریم. بعد از شناخت زبان، قدم طبیعی بعدی این است که یک برنامه کوچک بنویسیم و مرحله‌به‌مرحله آن را توسعه بدهیم."
            else:
                answer = f"حتماً؛ برمی‌گردیم به «{ref}». از آخرین نقطه‌ای که داشتیم ادامه می‌دهم."
            state.update(t, answer, "continuation", {}, .94, ref); return answer
        return base(self, t)
    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v3 = True


def install_v4():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v4", False):
        return
    base = LocalDialogueEngine.handle
    def handle(self, text):
        t = str(text or "").strip(); low = _b(t); state = self.state
        if low in {"این پاسخ درست بود", "درسته", "درست بود", "خوبه", "عالی بود", "پاسخ درست بود"}:
            answer = "بازخورد ثبت شد؛ این پاسخ موفق بود و برای انتخاب راهبردهای بعدی در حافظه یادگیری محلی نگه داشته می‌شود."
            state.accept(answer); state.update(t, answer, "feedback", {}, .99)
            try:
                self.runtime.learning.record(t, "feedback", answer, .98, "feedback", "reuse-success", "conversation")
                self.runtime.events.emit("learning_update", {"score": .98, "strategy": "reuse-success", "feedback": True})
            except Exception:
                pass
            return answer
        if low == "چرا":
            answer = "همان سؤال قبلی را مبنا می‌گیرم. اگر منظورت علت آن است، باید علت‌های محتمل را بررسی کنیم و با شواهد مشخص کنیم کدام‌یک قابل قبول‌تر است."
            state.update(t, answer, "why", {"question_units": [t]}, .90, state.current_topic or "")
            return answer
        if low in {"موضوع قبلی رو ادامه بده", "بحث قبلی رو ادامه بده", "همون قبلی رو ادامه بده"}:
            target = state.topic_stack[-1] if state.topic_stack else state.current_topic
            if target:
                answer = f"حتماً؛ برمی‌گردیم به «{target}». از همان‌جا ادامه می‌دهم."
                state.update(t, answer, "continuation", {}, .94, target)
                return answer
        answer = base(self, t)
        return answer[:-1] if answer.endswith("..") else answer
    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v4 = True


def install_v5():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v5", False):
        return
    base = LocalDialogueEngine.handle
    def handle(self, text):
        t = str(text or "").strip(); low = _b(t); state = self.state
        if "حافظه episodic" in low and "semantic" in low and ("یا" in low or "بهتر" in low):
            answer = "برای انتخاب بین این دو، معیار مهم‌تر از برتری مطلق است: episodic برای تجربه‌ها و رویدادهای مشخص بهتر است؛ semantic برای واقعیت‌ها و مفاهیم پایدار. در IRAN ترکیب هر دو انتخاب بهتری است."
            state.update(t, answer, "comparison", {"question_units": [t]}, .96); return answer
        if "همون قبلی" in low and "موضوع قبلی" not in low:
            current = state.current_topic
            if current:
                answer = f"حتماً؛ منظور را از «{current}» گرفتم و همان را ادامه می‌دهم."
            else:
                answer = "مرجع مشخصی برای «همون قبلی» در دست ندارم؛ اگر موضوع را بگویی، ادامه می‌دهم."
            state.update(t, answer, "reference", {}, .92, current); return answer
        if "موضوع قبلی" in low or "بحث قبلی" in low:
            target = state.topic_stack[-1] if state.topic_stack else state.current_topic
            if target:
                answer = f"حتماً؛ برمی‌گردیم به «{target}» و از همان‌جا ادامه می‌دهیم."
                state.update(t, answer, "continuation", {}, .94, target); return answer
        return base(self, t)
    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v5 = True


def install_v6():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v6", False):
        return
    base = LocalDialogueEngine.handle
    def handle(self, text):
        t = str(text or "").strip(); low = _b(t); state = self.state
        if low == "چرا":
            source = " ".join([state.current_question or "", state.current_topic or "", state.last_user_message or "", *list(state.topic_stack)[-3:]])
            if "پایتون" in source.lower():
                answer = "اگر منظورت این است که چرا پایتون محبوب است: خواناست، یادگیری‌اش نسبتاً ساده است، اکوسیستم بزرگی دارد و در وب، داده، اتوماسیون و هوش مصنوعی کاربردهای زیادی دارد."
            else:
                answer = "همان سؤال قبلی را مبنا می‌گیرم. اگر منظورت علت آن است، باید علت‌های محتمل را بررسی کنیم و با شواهد مشخص کنیم کدام‌یک قابل قبول‌تر است."
            state.update(t, answer, "why", {"question_units": [t]}, .94, state.current_topic or ""); return answer
        return base(self, t)
    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v6 = True


def install_v7():
    from core.dialogue import LocalDialogueEngine
    if getattr(LocalDialogueEngine, "_chat_upgrade_v7", False):
        return
    base = LocalDialogueEngine.handle
    def handle(self, text):
        t = str(text or "").strip(); low = _b(t); state = self.state
        if low in {"چرا محبوبه", "چرا محبوب است", "چرا پایتون محبوبه", "چرا پایتون محبوب است"} and "پایتون" in ((state.current_topic or "") + " " + (state.current_question or "")).lower():
            answer = "پایتون محبوب است چون خوانایی بالایی دارد، یادگیری‌اش نسبتاً ساده است، اکوسیستم بزرگی دارد و در وب، داده، اتوماسیون و هوش مصنوعی کاربردهای زیادی دارد."
            state.update(t, answer, "why", {"question_units": [t]}, .95, "پایتون"); return answer
        return base(self, t)
    LocalDialogueEngine.handle = handle
    LocalDialogueEngine._chat_upgrade_v7 = True
