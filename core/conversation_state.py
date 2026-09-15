import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

REF_WORDS = ('این', 'همین', 'اون', 'آن', 'قبلی', 'همون', 'همونو', 'بالایی', 'این بخش', 'این جواب', 'این مشکل', 'روش قبلی', 'موضوع قبلی')
CORRECTION_WORDS = ('نه', 'منظورم', 'اشتباهه', 'اشتباه است', 'من اینو نگفتم', 'نه منظورم')
FOLLOW_UPS = ('چرا', 'چطور', 'چگونه', 'پس چی', 'حالا چی', 'ادامه بده', 'بیشتر توضیح بده', 'بهترش کن', 'توضیح بده', 'مثال بزن', 'ساده تر بگو', 'کوتاه تر بگو')


def clean(text):
    return re.sub(r'\s+', ' ', str(text).strip().replace('ي', 'ی').replace('ك', 'ک'))


def substantive(text):
    return len(re.findall(r'[آ-یA-Za-z0-9]+', clean(text))) >= 2


@dataclass
class Turn:
    role: str
    content: str
    topic: str = ''
    goal: str = ''


@dataclass
class ConversationState:
    turns: list[dict] = field(default_factory=list)
    current_topic: str = ''
    topic_stack: list[str] = field(default_factory=list)
    active_goal: str = ''
    current_question: str = ''
    last_user_message: str = ''
    last_assistant_answer: str = ''
    last_answer_type: str = ''
    references: dict[str, str] = field(default_factory=dict)
    entities: list[str] = field(default_factory=list)
    user_facts: dict[str, str] = field(default_factory=dict)
    user_preferences: dict[str, str] = field(default_factory=dict)
    unresolved_questions: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    accepted_answers: list[str] = field(default_factory=list)
    rejected_answers: list[str] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    conversation_confidence: float = 0.5
    state_path: str = ''

    def __post_init__(self):
        if self.state_path:
            self.load(self.state_path)

    @property
    def topic(self):
        return self.current_topic

    @topic.setter
    def topic(self, value):
        self.current_topic = clean(value)

    @property
    def goal(self):
        return self.active_goal

    @goal.setter
    def goal(self, value):
        self.active_goal = clean(value)

    @property
    def last_user(self):
        return self.last_user_message

    @last_user.setter
    def last_user(self, value):
        self.last_user_message = clean(value)

    @property
    def last_assistant(self):
        return self.last_assistant_answer

    @last_assistant.setter
    def last_assistant(self, value):
        self.last_assistant_answer = clean(value)

    @property
    def referent(self):
        return self.references.get('current', '')

    @referent.setter
    def referent(self, value):
        value = clean(value)
        if value:
            self.references['current'] = value

    @property
    def correction(self):
        return self.corrections[-1] if self.corrections else ''

    def update(self, user_text, assistant_text='', parsed=None, answer_type=''):
        user_text, assistant_text = clean(user_text), clean(assistant_text)
        parsed = parsed or {}
        previous = self.current_topic
        self.last_user_message = user_text
        self.current_question = user_text if any(x in user_text for x in ('؟', '?', 'چرا', 'چطور', 'چگونه', 'آیا')) else self.current_question
        goal = clean(parsed.get('goal', ''))
        if goal:
            self.active_goal = goal
        entities = parsed.get('entities') or []
        for item in entities:
            value = clean(item.get('text', '')) if isinstance(item, dict) else clean(item)
            if substantive(value) and value not in self.entities:
                self.entities.append(value)
        if self._is_correction(user_text):
            self._record_correction(user_text)
        reference = self.resolve_reference(user_text)
        if reference:
            self.referent = reference
        elif not self._is_follow_up(user_text) and not self._is_correction(user_text) and substantive(user_text):
            self.set_topic(user_text)
        if self._is_follow_up(user_text) and not self.current_topic:
            self.set_topic(self.last_user_message)
        if assistant_text:
            self.last_assistant_answer = assistant_text
            self.last_answer_type = answer_type or self.last_answer_type
        self.turns.append(asdict(Turn('user', user_text, self.current_topic, self.active_goal)))
        if assistant_text:
            self.turns.append(asdict(Turn('assistant', assistant_text, self.current_topic, self.active_goal)))
        self.turns = self.turns[-80:]
        if previous and self.current_topic and previous != self.current_topic and substantive(previous):
            if previous not in self.topic_stack:
                self.topic_stack.append(previous)
            self.topic_stack = self.topic_stack[-20:]
        self.conversation_confidence = self._confidence(reference, user_text)
        self.save()

    def set_topic(self, topic):
        topic = clean(topic)
        if not topic:
            return
        if self.current_topic and self.current_topic != topic and substantive(self.current_topic):
            self.topic_stack.append(self.current_topic)
            self.topic_stack = self.topic_stack[-20:]
        self.current_topic = topic
        self.references['current'] = topic

    def previous_topic(self):
        return self.topic_stack[-1] if self.topic_stack else ''

    def restore_previous_topic(self):
        if not self.topic_stack:
            return self.current_topic
        previous = self.topic_stack.pop()
        if self.current_topic and self.current_topic != previous:
            self.topic_stack.append(self.current_topic)
        self.current_topic = previous
        self.references['current'] = previous
        self.save()
        return previous

    def resolve_reference(self, text):
        text = clean(text)
        if 'موضوع قبلی' in text or 'برگردیم' in text:
            return self.restore_previous_topic()
        if 'همون بحث اول' in text and self.topic_stack:
            return self.topic_stack[0]
        if not any(w in text for w in REF_WORDS):
            return ''
        candidate = self.current_topic or self.active_goal or self.last_user_message
        if candidate:
            for word in REF_WORDS:
                if word in text:
                    self.references[word] = candidate
        return candidate

    def record_acceptance(self, answer):
        self.accepted_answers.append(clean(answer)); self.accepted_answers = self.accepted_answers[-30:]; self.save()

    def record_rejection(self, answer):
        self.rejected_answers.append(clean(answer)); self.rejected_answers = self.rejected_answers[-30:]; self.save()

    def _record_correction(self, text):
        self.corrections.append(text); self.corrections = self.corrections[-30:]
        target = re.split(r'منظورم\s*', text, maxsplit=1)[-1].strip(' :،')
        if substantive(target) and target != text:
            self.set_topic(target)
            self.references['correction'] = target

    def _is_follow_up(self, text):
        normalized = clean(text).rstrip('؟?').replace('‌', ' ')
        return any(normalized == x or normalized.startswith(x + ' ') for x in FOLLOW_UPS)

    def _is_correction(self, text):
        return any(clean(text).startswith(x) for x in CORRECTION_WORDS)

    def _confidence(self, reference, text):
        if self._is_correction(text): return 0.95
        if reference: return 0.88
        if self._is_follow_up(text): return 0.82 if self.current_topic else 0.45
        return 0.72 if substantive(text) else 0.55

    def prompt_context(self):
        rows = []
        if self.current_topic: rows.append(f'current_topic={self.current_topic}')
        if self.active_goal: rows.append(f'active_goal={self.active_goal}')
        if self.referent: rows.append(f'current_referent={self.referent}')
        if self.correction: rows.append(f'latest_correction={self.correction}')
        if self.topic_stack: rows.append('topic_stack=' + ' | '.join(self.topic_stack[-5:]))
        if self.unresolved_questions: rows.append('unresolved=' + ' | '.join(self.unresolved_questions[-3:]))
        return '\n'.join(rows)

    def snapshot(self):
        data = asdict(self)
        data.pop('state_path', None)
        return data

    def save(self, path=None):
        path = path or self.state_path
        if not path:
            return
        self.state_path = str(path)
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')

    def load(self, path=None):
        path = path or self.state_path
        if not path:
            return
        p = Path(path)
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            for key, value in data.items():
                if key != 'state_path' and hasattr(self, key):
                    setattr(self, key, value)
        except (OSError, ValueError, TypeError):
            return
