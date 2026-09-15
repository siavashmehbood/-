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
            return self._format_facts(facts)
        return 'هنوز واقعیت صریح و پایداری درباره شما در حافظه ندارم.'

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
