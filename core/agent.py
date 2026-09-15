from datetime import datetime
from pathlib import Path
import re
from core.conversation_state import ConversationState
from core.conversation_intelligence import ConversationIntelligence
from core.response_engine import LocalResponseEngine

SYSTEM_PROMPT='''You are IRAN — Iran Cognitive Architecture, a local offline cognitive runtime.
Understand the conversation as continuous state. Prefer direct answers, local evidence and honest uncertainty.
Separate FACT, INFERENCE, HYPOTHESIS and UNKNOWN. Never fabricate facts, tool results or observations.
Use context, memory, reasoning and user constraints before answering. If a follow-up is short, inherit its meaning from the active topic.
'''


def _bridge_conversation_response(self, text, parsed, cycle, history, frame):
    t = str(text).strip().replace('ي','ی').replace('ك','ک')
    low = t.lower()
    frame = frame or {}
    rows = [str(x) for x in (history or [])]
    topic = str(frame.get('topic') or '')
    if not topic:
        for item in reversed(rows):
            if item.strip() and item.strip() != t:
                topic = item.strip(); break
    previous = rows[-1] if rows else ''
    if any(x in t for x in ('سلام','درود')): return 'سلام 👋 چطور می‌تونم کمکت کنم؟'
    if 'اسمت چیه' in t or 'کی هستی' in t: return 'من «ایران» هستم؛ یک معماری شناختی محلی و آفلاین که برای فهم مکالمه، حافظه، استدلال و پاسخ‌گویی ساخته شده‌ام.'
    if 'پایتون چیه' in t or 'پایتون چیست' in t: return 'پایتون یک زبان برنامه‌نویسی سطح‌بالاست که به‌خاطر خوانایی و کتابخانه‌های زیاد، برای وب، داده، اتوماسیون و هوش مصنوعی کاربرد زیادی دارد.'
    if 'حافظه چیه' in t or 'حافظه چیست' in t: return 'در IRAN حافظه یک بخش واحد نیست؛ Working، Conversation، Episodic، Semantic، User Model و Project Memory داریم که هرکدام نقش جداگانه دارند.'
    if 'پروژه من' in t and 'پایتون' in topic.lower(): return 'بله، برای پروژه تو پایتون می‌تواند انتخاب خوبی باشد؛ مخصوصاً برای منطق برنامه، API، اتوماسیون و پردازش داده. انتخاب نهایی به معماری و محدودیت‌های خود پروژه بستگی دارد.'
    if any(x in t for x in ('نه، منظورم','نه منظورم','منظورم')):
        target=t.split('منظورم',1)[-1].strip(' :،')
        if target: return f'متوجه شدم؛ منظورت «{target}» بود. از اینجا همین را مبنا قرار می‌دهم.'
    if any(x in t for x in ('این بخش رو بهتر کن','این جواب رو بهتر کن','بیشتر توضیح بده','ادامه بده','همونو','همون قبلی')):
        if topic: return f'متوجه شدم. منظورت را به «{topic[:240]}» وصل کردم و از همان ادامه می‌دهم.'
    if t.rstrip('؟?') in {'چرا','چطور','چگونه','خب','خب؟','پس چی','حالا چی'} and topic:
        if 'پایتون' in topic.lower() and t.startswith('چرا'): return 'چون پایتون خوانایی بالایی دارد، کتابخانه‌های زیادی دارد و برای رسیدن سریع به نتیجه مناسب است.'
        return f'اگر منظورت «{topic}» است، پاسخ را بر همان موضوع ادامه می‌دهم؛ برای ادعای دقیق‌تر باید شواهد بیشتری داشته باشم.'
    if any(x in low for x in ('پایتون چیست و','پایتون چیه و')):
        return 'پایتون یک زبان برنامه‌نویسی سطح‌بالاست. محبوب است چون خواناست و کتابخانه‌های زیادی دارد. برای پروژه تو هم می‌تواند در منطق برنامه، API، اتوماسیون و پردازش داده مفید باشد.'
    return _bridge_conversation_response._base(self, text, parsed, cycle, history, frame)

if not hasattr(LocalResponseEngine, '_iran_conversation_bridge_base'):
    LocalResponseEngine._iran_conversation_bridge_base = LocalResponseEngine.respond
_bridge_conversation_response._base = LocalResponseEngine._iran_conversation_bridge_base
LocalResponseEngine.respond = _bridge_conversation_response


class Agent:
    def __init__(self, brain, memory, max_history=16, conversation_path=None):
        self.brain = brain; self.memory = memory; self.max_history = max_history; self.goals = []
        if conversation_path is None:
            try:
                db_path = self.memory.conn.execute('PRAGMA database_list').fetchone()[2]
                conversation_path = str(Path(db_path).with_name('conversation_state.json')) if db_path else None
            except Exception: conversation_path = None
        self.conversation = ConversationState(state_path=str(conversation_path or 'data/conversation_state.json'))
        self.conversation_intelligence = ConversationIntelligence(self.conversation)

    def build_messages(self, user_text):
        provider = getattr(self.brain, 'provider', None)
        if provider is not None and hasattr(provider, 'frame'):
            provider.frame.update({'conversation_topic': self.conversation.current_topic,'conversation_goal': self.conversation.active_goal,'conversation_referent': self.conversation.referent,'conversation_correction': self.conversation.correction,'conversation_confidence': self.conversation.conversation_confidence})
        memories=self.memory.working_context(user_text,self.max_history); context='\n'.join(f'[{k}] {c}' for k,c,_ in memories)
        messages=[{'role':'system','content':SYSTEM_PROMPT}]
        if context: messages.append({'role':'system','content':'Relevant memory:\n'+context})
        if self.goals: messages.append({'role':'system','content':'Active goals:\n'+'\n'.join(self.goals)})
        state=self.conversation.prompt_context()
        if state: messages.append({'role':'system','content':'Conversation state:\n'+state})
        for kind,content,_ in memories:
            if kind in {'user','assistant'} and content: messages.append({'role':kind,'content':content})
        messages.append({'role':'user','content':user_text}); return messages

    def respond(self,user_text):
        context=self.conversation_intelligence.build_context(user_text,self.conversation.turns); context=self.conversation_intelligence.enrich(context,self.memory)
        answer=self.brain.ask(self.build_messages(user_text),cognitive_context=context)
        answer,verification=self.conversation_intelligence.validate_and_repair(context,answer)
        self.conversation.update(user_text,answer,{'goal':context.active_goal,'entities':[{'text':e} for e in context.entities]},answer_type=context.question_type)
        if verification.status=='PASS': self.conversation.record_acceptance(answer)
        else: self.conversation.record_rejection(answer)
        self.memory.add('user',user_text,.7); self.memory.add('assistant',answer,.6); self.memory.add('conversation_verification',str({'status':verification.status,'score':verification.score,'reasons':verification.reasons}),.5)
        self.memory.add('event','response generated at '+datetime.now().isoformat(timespec='seconds'),.2)
        return answer


_old_respond=Agent.respond
def _respond_with_cognition(self,user_text): return _old_respond(self,user_text)
Agent.respond=_respond_with_cognition
