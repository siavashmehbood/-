import re
from dataclasses import dataclass, field

REF_WORDS = ('این', 'همین', 'اون', 'آن', 'قبلی', 'همون', 'همونو', 'این بخش', 'این جواب', 'این مشکل')
CORRECTION_WORDS = ('نه', 'منظورم', 'اشتباهه', 'اشتباه است', 'من اینو نگفتم', 'نه منظورم')
FOLLOW_UPS = ('چرا؟', 'چطور؟', 'چگونه؟', 'پس چی؟', 'حالا چی؟', 'ادامه بده', 'بیشتر توضیح بده', 'بهترش کن')


def clean(text):
    return re.sub(r'\s+', ' ', str(text).strip().replace('ي', 'ی').replace('ك', 'ک'))


def substantive(text):
    return len(re.findall(r'[آ-یA-Za-z0-9]+', clean(text))) >= 2


@dataclass
class ConversationState:
    topic: str = ''
    goal: str = ''
    last_user: str = ''
    last_assistant: str = ''
    referent: str = ''
    correction: str = ''
    unresolved: list = field(default_factory=list)
    turns: int = 0

    def update(self, user_text, assistant_text='', parsed=None):
        user_text, assistant_text = clean(user_text), clean(assistant_text)
        parsed = parsed or {}
        self.turns += 1
        self.last_user = user_text
        if assistant_text:
            self.last_assistant = assistant_text
        goal = clean(parsed.get('goal', ''))
        entities = parsed.get('entities') or []
        entity = clean(entities[0].get('text', '')) if entities and isinstance(entities[0], dict) else ''
        if goal:
            self.goal = goal
        if entity and substantive(entity):
            self.topic = entity
        elif self._is_follow_up(user_text):
            self.referent = self.referent or self.topic or self.last_user
            self.topic = self.referent
        elif substantive(user_text):
            self.topic = user_text
        ref = self.resolve_reference(user_text)
        if ref:
            self.referent = ref
            self.topic = ref
        if self._is_correction(user_text):
            self.correction = user_text
            target = re.split(r'منظورم\s*', user_text, maxsplit=1)[-1].strip(' :،')
            if substantive(target) and target != user_text:
                self.topic = target
                self.referent = target
            self.unresolved.append(user_text)

    def resolve_reference(self, text):
        text = clean(text)
        if not any(w in text for w in REF_WORDS):
            return ''
        return self.topic or self.goal or self.last_user

    def _is_follow_up(self, text):
        text = clean(text).rstrip('؟?') + '؟'
        return text in FOLLOW_UPS or any(text.startswith(x.rstrip('؟?')) for x in FOLLOW_UPS)

    def _is_correction(self, text):
        return any(text.startswith(x) for x in CORRECTION_WORDS)

    def prompt_context(self):
        rows = []
        if self.topic: rows.append(f'current_topic={self.topic}')
        if self.goal: rows.append(f'active_goal={self.goal}')
        if self.referent: rows.append(f'current_referent={self.referent}')
        if self.correction: rows.append(f'latest_correction={self.correction}')
        if self.unresolved: rows.append('unresolved=' + ' | '.join(self.unresolved[-3:]))
        return '\n'.join(rows)
