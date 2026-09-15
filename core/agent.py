from datetime import datetime
from core.conversation_state import ConversationState
from core.conversation_intelligence import ConversationIntelligence

SYSTEM_PROMPT='''You are IRAN — Iran Cognitive Architecture, a local offline cognitive runtime.
Understand the conversation as continuous state. Prefer direct answers, local evidence and honest uncertainty.
Separate FACT, INFERENCE, HYPOTHESIS and UNKNOWN. Never fabricate facts, tool results or observations.
Use context, memory, reasoning and user constraints before answering. If a follow-up is short, inherit its meaning from the active topic.
'''


class Agent:
    def __init__(self, brain, memory, max_history=16, conversation_path=None):
        self.brain = brain; self.memory = memory; self.max_history = max_history; self.goals = []
        self.conversation = ConversationState(state_path=str(conversation_path or ''))
        self.conversation_intelligence = ConversationIntelligence(self.conversation)

    def build_messages(self, user_text):
        provider = getattr(self.brain, 'provider', None)
        if provider is not None and hasattr(provider, 'frame'):
            provider.frame.update({'conversation_topic': self.conversation.current_topic,
                                   'conversation_goal': self.conversation.active_goal,
                                   'conversation_referent': self.conversation.referent,
                                   'conversation_correction': self.conversation.correction,
                                   'conversation_confidence': self.conversation.conversation_confidence})
        memories = self.memory.working_context(user_text, self.max_history)
        context = '\n'.join(f'[{k}] {c}' for k, c, _ in memories)
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        if context: messages.append({'role': 'system', 'content': 'Relevant memory:\n' + context})
        if self.goals: messages.append({'role': 'system', 'content': 'Active goals:\n' + '\n'.join(self.goals)})
        state = self.conversation.prompt_context()
        if state: messages.append({'role': 'system', 'content': 'Conversation state:\n' + state})
        for kind, content, _ in memories:
            if kind in {'user', 'assistant'} and content: messages.append({'role': kind, 'content': content})
        messages.append({'role': 'user', 'content': user_text})
        return messages

    def _local_answer(self, text, context):
        t = str(text).strip().replace('ي', 'ی').replace('ك', 'ک')
        topic = context.current_topic or self.conversation.current_topic
        previous = self.conversation.last_assistant_answer
        provider = getattr(self.brain, 'provider', None)
        if any(x in t for x in ('سلام', 'درود')): return 'سلام 👋 چطور می‌تونم کمکت کنم؟'
        if any(x in t for x in ('ممنون', 'مرسی', 'سپاس', 'تشکر')): return 'خواهش می‌کنم 🌱'
        if context.question_type == 'multi_intent':
            lower = t.lower()
            parts = []
            if 'پایتون' in lower:
                parts.append('پایتون یک زبان برنامه‌نویسی سطح‌بالاست که برای وب، داده، اتوماسیون و هوش مصنوعی استفاده می‌شود.')
            if 'چرا' in lower and 'پایتون' in lower:
                parts.append('محبوب است چون خوانایی بالایی دارد، کتابخانه‌های زیادی دارد و برای رسیدن سریع به نتیجه مناسب است.')
            if 'پروژه' in lower:
                parts.append('برای پروژه تو می‌تواند برای منطق برنامه، API، اتوماسیون یا پردازش داده مفید باشد؛ انتخاب دقیق به نوع پروژه بستگی دارد.')
            if parts: return '\n'.join(f'{i+1}. {part}' for i, part in enumerate(parts))
        if context.question_type == 'follow_up' or self.conversation._is_follow_up(t):
            if 'ساده' in t and previous: return 'ساده‌ترش اینه: ' + previous.split('。')[0].strip(' .')
            if 'کوتاه' in t and previous: return previous[:240].rstrip() + ('…' if len(previous) > 240 else '')
            if 'ادامه' in t and previous: return f'ادامه همان بحث: {previous[:180]} سپس بخش بعدی را بررسی می‌کنیم.'
            if 'مثال' in t and topic: return f'مثال ساده درباره «{topic}»: اول یک نمونه کوچک می‌سازی، نتیجه را می‌سنجی و بعد گسترشش می‌دهی.'
            if ('چرا' in t or 'چطور' in t) and topic:
                if 'پایتون' in topic.lower() and 'چرا' in t:
                    return 'چون پایتون خوانایی بالایی دارد، کتابخانه‌های زیادی دارد و برای وب، اتوماسیون و تحلیل داده سریع به نتیجه می‌رساند.'
                if 'پایتون' in topic.lower() and 'چطور' in t:
                    return 'برای پروژه‌ات می‌توانی از پایتون برای منطق برنامه، API، اتوماسیون یا پردازش داده استفاده کنی؛ انتخاب دقیق به نوع پروژه و محدودیت‌هایش بستگی دارد.'
                return f'اگر منظورت «{topic}» است، باید علت یا روش را با توجه به همان موضوع بررسی کنیم؛ اطلاعات فعلی برای ادعای دقیق کافی نیست.'
        if self.conversation._is_correction(t):
            target = t.split('منظورم', 1)[-1].strip(' :،')
            if target and target != t: return f'متوجه شدم؛ مرجع قبلی را به «{target}» اصلاح کردم و از اینجا همان را مبنا قرار می‌دهم.'
        if ('موضوع قبلی' in t or 'بحث قبلی' in t or 'برگردیم' in t) and self.conversation.previous_topic():
            return f'برمی‌گردیم به موضوع قبلی: «{self.conversation.previous_topic()}».'
        if ('اسم پروژه' in t or 'نام پروژه' in t): return 'اسم پروژه «IRAN» است؛ معماری آن Iran Cognitive Architecture است.'
        if provider is not None and hasattr(provider, '_special'):
            special = provider._special(t)
            if special: return special
        return None

    def respond(self, user_text):
        context = self.conversation_intelligence.build_context(user_text, self.conversation.turns)
        context = self.conversation_intelligence.enrich(context, self.memory)
        local = self._local_answer(user_text, context)
        answer = local if local is not None else self.brain.ask(self.build_messages(user_text), cognitive_context=context)
        answer, verification = self.conversation_intelligence.validate_and_repair(context, answer)
        self.conversation.update(user_text, answer, {'goal': context.active_goal, 'entities': [{'text': e} for e in context.entities]}, answer_type=context.question_type)
        if verification.status == 'PASS': self.conversation.record_acceptance(answer)
        else: self.conversation.record_rejection(answer)
        self.memory.add('user', user_text, 0.7); self.memory.add('assistant', answer, 0.6)
        self.memory.add('conversation_verification', str({'status': verification.status, 'score': verification.score, 'reasons': verification.reasons}), 0.5)
        self.memory.add('event', 'response generated at ' + datetime.now().isoformat(timespec='seconds'), 0.2)
        return answer


_old_respond = Agent.respond

def _respond_with_cognition(self, user_text):
    return _old_respond(self, user_text)

Agent.respond = _respond_with_cognition
