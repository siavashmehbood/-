class ConversationRouter:
    """Single visible-response boundary for explicit conversational facts."""
    def __init__(self, runtime):
        self.runtime = runtime

    def answer(self, text):
        t = str(text).strip()
        if not self._asks_about_user(t):
            return None
        model = getattr(self.runtime, 'user_model', None)
        if model is not None:
            facts = model.current_profile(limit=20) if hasattr(model, 'current_profile') else model.facts(limit=20)
        else:
            facts = []
        if facts:
            if self._asks_name(t):
                rows = [f for f in facts if f.get('predicate') == 'name']
                if rows:
                    return f"اسمت «{rows[0].get('object')}» است."
            if self._asks_likes(t):
                rows = [f for f in facts if f.get('predicate') == 'likes']
                if rows:
                    return 'چیزهایی که گفتی دوست داری: ' + '، '.join(f"«{f.get('object')}»" for f in rows) + '.'
            return self._format_facts(facts)
        return 'هنوز اطلاعات مشخصی درباره خودت به من نگفتی.'

    @staticmethod
    def _asks_name(text):
        return any(x in text for x in ('اسم من چی بود', 'نام من چی بود', 'اسمم چی بود', 'نامم چی بود'))

    @staticmethod
    def _asks_likes(text):
        return any(x in text for x in ('چه چیزی دوست داشتم', 'چی دوست داشتم', 'چه چیزهایی دوست دارم', 'من چی دوست دارم', 'علایق من چیه', 'علاقه من چیه'))

    @staticmethod
    def _asks_about_user(text):
        markers = (
            'درباره خودم', 'در مورد خودم', 'راجع به خودم',
            'درباره من', 'در مورد من', 'راجع به من',
            'من چی گفتم', 'من چه گفتم', 'یادت هست من',
            'چی درباره خودم', 'چه چیزی درباره خودم',
            'چه چیزی در مورد خودم'
        )
        return any(x in text for x in markers)

    @staticmethod
    def _format_facts(facts):
        lines = []
        for fact in facts:
            p, obj = fact.get('predicate'), fact.get('object')
            if p == 'role' and obj == 'creator':
                lines.append('• شما سازنده پروژه IRAN هستید.')
            elif p == 'goal':
                lines.append(f'• هدفی که خودتان صریحاً گفتید: {obj}')
            elif p == 'likes':
                lines.append(f'• گفتید «{obj}» را دوست دارید.')
            elif p == 'dislikes':
                lines.append(f'• گفتید «{obj}» را دوست ندارید.')
            elif p == 'name':
                lines.append(f'• نام شما «{obj}» است.')
            else:
                lines.append(f'• {p}: {obj}')
        return 'تا این لحظه این اطلاعات صریح را از خودتان دارم:\n' + '\n'.join(lines)


# v0.39: cover direct personal-memory questions in the canonical dialogue path.
_original_asks_about_user = ConversationRouter._asks_about_user
def _asks_about_user_v39(text):
    t = str(text)
    markers = (
        '\u0627\u0633\u0645 \u0645\u0646 \u0686\u06cc \u0628\u0648\u062f',
        '\u0646\u0627\u0645 \u0645\u0646 \u0686\u06cc \u0628\u0648\u062f',
        '\u0686\u0647 \u0686\u06cc\u0632\u06cc \u062f\u0648\u0633\u062a \u062f\u0627\u0634\u062a\u0645',
        '\u0686\u06cc \u062f\u0648\u0633\u062a \u062f\u0627\u0634\u062a\u0645'
    )
    return _original_asks_about_user(t) or any(m in t for m in markers)
ConversationRouter._asks_about_user = staticmethod(_asks_about_user_v39)
