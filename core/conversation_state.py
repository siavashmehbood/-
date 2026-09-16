import re
from dataclasses import dataclass, field


REF_WORDS = ('این', 'همین', 'اون', 'آن', 'قبلی', 'همون', 'همونو', 'این بخش', 'این جواب', 'این مشکل')
CORRECTION_WORDS = ('نه', 'منظورم', 'اشتباهه', 'اشتباه است', 'من اینو نگفتم', 'نه منظورم')
FOLLOW_UPS = ('چرا؟', 'چطور؟', 'چگونه؟', 'پس چی؟', 'حالا چی؟', 'ادامه بده', 'بیشتر توضیح بده', 'بهترش کن')


def clean(text):
    return re.sub(r'\s+', ' ', str(text).strip().replace('ي', 'ی').replace('ك', 'ک'))


def substantive(text):
    text = clean(text)
    return len(re.sub(r'[^آ-یA-Za-z0-9]', '', text)) >= 2


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
        user_text = clean(user_text)
        assistant_text = clean(assistant_text)
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
        # A follow-up carries no new goal of its own. Keeping the previous goal here
        # is intentional, but it must not be overwritten by the follow-up text, and a
        # real topic change must be able to move the goal forward. Previously the goal
        # was set once and then froze for the rest of the conversation, so a later
        # topic switch still reported the first question as `active_goal`.
        elif entity and substantive(entity):
            self.goal = entity
        if entity and substantive(entity):
            self.topic = entity
        elif self._is_follow_up(user_text):
            self.referent = self.referent or self.topic or self.last_user
            self.topic = self.referent
        elif substantive(user_text) and not self._is_follow_up(user_text):
            self.topic = user_text
        ref = self.resolve_reference(user_text)
        if ref:
            self.referent = ref
            self.topic = ref
        if self._is_correction(user_text):
            self.correction = user_text
            self.unresolved.append(user_text)

    def resolve_reference(self, text):
        text = clean(text)
        if 'اینترنت' in text:
            return ''
        if not any(w in text for w in REF_WORDS):
            return ''
        if self.topic and substantive(self.topic):
            return self.topic
        if self.goal and substantive(self.goal):
            return self.goal
        if substantive(self.last_user):
            return self.last_user
        return ''

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
