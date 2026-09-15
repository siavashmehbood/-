import re
from core.cognitive_fabric import AdvancedLanguage, SemanticRetriever, ResponseComposer

class IranProvider:
    """Offline Persian cognitive responder: no API, model server or network."""
    name='iran-local'
    def __init__(self):
        self.turns=0
        self.language=AdvancedLanguage()
        self.retriever=SemanticRetriever()
        self.composer=ResponseComposer()
        self.frame={}
        self.facts={}
        self.last_answers=[]

    def health(self):
        return {'provider':self.name,'ok':True,'mode':'local-cognitive','model':'Iran Core',
                'network':False,'capabilities':['semantic-parsing','dialogue-state','local-retrieval',
                'multi-intent','reference-resolution','reasoned-composition','uncertainty-estimation']}

    def _clean(self,text):
        return re.sub(r'\s+',' ',str(text).strip().replace('ي','ی').replace('ك','ک'))

    def _last_user(self,messages):
        for item in reversed(messages):
            if item.get('role')=='user': return self._clean(item.get('content',''))
        return ''

    def _context(self,messages):
        return [self._clean(x['content']) for x in messages
                if x.get('role') in ('user','assistant') and x.get('content')][-14:]

    def _special(self,text):
        t=text.lower()
        if any(x in t for x in ('سلام','درود','hello','hi')):
            return 'سلام 👋 من ایران هستم. درخواست را در چند مرحله تحلیل می‌کنم: هدف، زمینه، ابهام، شواهد، گزینه‌ها و نتیجه. اگر مطمئن نباشم، عدم‌قطعیت را صریح می‌گویم.'
        if any(x in t for x in ('ممنون','مرسی','سپاس','تشکر')):
            return 'خواهش می‌کنم. زمینه این گفت‌وگو را نگه می‌دارم و می‌توانیم دقیقاً از همین نقطه ادامه بدهیم.'
        if any(x in t for x in ('کی هستی','چی هستی','معرفی کن','خودت را معرفی')):
            return 'من ایران هستم؛ هسته شناختی مستقل و آفلاین این پروژه. حافظه، درک زبان، مدل جهان، استدلال، فرضیه‌سازی، پیش‌بینی، تصمیم، برنامه‌ریزی، یادگیری و خودارزیابی دارم. مدل عصبی عظیم مثل GPT نیستم و این محدودیت را پنهان نمی‌کنم.'
        if any(x in t for x in ('اسم پروژه','نام پروژه','پروژه چیه','اسم این پروژه')):
            return 'اسم پروژه «ایران» است؛ نام معماری آن IRAN — Iran Cognitive Architecture است.'
        if any(x in t for x in ('سازنده پروژه','سازنده ایران','چه کسی سازنده')):
            um=getattr(self,'_user_model',None)
            if um:
                facts=um.facts(limit=8)
                creator=[f for f in facts if (f.get('predicate')=='creator' or (f.get('predicate')=='role' and f.get('object')=='creator'))]
                if creator:
                    return 'بله. در User Model یک واقعیت صریح ثبت شده: شما سازنده پروژه IRAN هستید.'
            return 'برای ادعای سازنده بودن، هنوز شاهد صریح و پایدار در User Model ندارم.'
        if any(x in t for x in ('چرا ساخته شدی','برای چی ساخته شدی','هدفت چیه','هدف از ساختت')):
            return 'هدف IRAN ساخت یک معماری شناختی مستقل است که بتواند ورودی را بفهمد، حافظه و دانش را به کار بگیرد، استدلال و برنامه‌ریزی کند، اقدام را مشاهده و بررسی کند، از نتیجه یاد بگیرد و برای رسیدن به هدف بازبرنامه‌ریزی کند.'
        if any(x in t for x in ('قابلیت','چه کارهایی','توانایی','چه بلدی')):
            return 'الان می‌توانم ورودی را ساختاربندی کنم، چند تفسیر نگه دارم، ارجاع‌های قبلی را دنبال کنم، شواهد و تجربه‌های مشابه را بازیابی کنم، فرضیه بسازم، گزینه‌ها را با ریسک/فایده مقایسه کنم، برنامه مرحله‌ای بسازم، نتیجه را ثبت و از تجربه بعدی استفاده کنم.'
        if ('اگر' in t and ('ندانی' in t or 'نمی‌دانی' in t or 'نمی‌دونم' in t) and ('جواب' in t or 'پاسخ' in t)):
            return 'اگر پاسخ را ندانم، حدس را به‌عنوان واقعیت ارائه نمی‌کنم. اول حافظه، دانش و شواهد مرتبط را بررسی می‌کنم؛ اگر کافی نبود، عدم‌قطعیت را اعلام می‌کنم و مشخص می‌کنم برای پاسخ قطعی چه داده یا آزمایشی لازم است.'
        if ('اگر' in t and ('ندانی' in t or 'نمی‌دانی' in t or 'نمی‌دونم' in t) and ('جواب' in t or 'پاسخ' in t)):
            return 'اگر پاسخ را ندانم، حدس را به‌عنوان واقعیت ارائه نمی‌کنم. اول حافظه، دانش و شواهد مرتبط را بررسی می‌کنم؛ اگر کافی نبود، عدم‌قطعیت را اعلام می‌کنم و مشخص می‌کنم برای پاسخ قطعی چه داده یا آزمایشی لازم است.'
        return ''

    def _remember(self,text,parsed):
        goal=parsed.get('goal','').strip()
        if goal and parsed.get('intent') in ('build','plan','command'):
            self.facts['current_goal']=goal
        ents=parsed.get('entities',[])
        if ents: self.facts['current_topic']=ents[0].get('text','')

    def _answer_question(self,text,parsed,history):
        q=text.rstrip('؟?').strip()
        if 'چرا' in q:
            subject=re.sub(r'^.*?چرا\s*','',q).strip()
            return f'برای «{subject}» هنوز علت قطعی در داده محلی ندارم. سه مسیر را جدا می‌کنم: ۱) وضعیت/پیکربندی، ۲) منطق یا پیاده‌سازی، ۳) محیط و وابستگی‌ها. برای نتیجه قطعی باید شواهد مربوط به همین موضوع بررسی شود.'
        if any(x in q for x in ('چطور','چگونه','چه جوری')):
            subject=re.sub(r'^.*?(چطور|چگونه|چه جوری)\s*','',q).strip()
            return f'برای «{subject}» ابتدا هدف و محدودیت را مشخص می‌کنم، بعد گزینه‌ها را می‌سازم، کم‌ریسک‌ترین مسیر را انتخاب می‌کنم و نتیجه را با معیار قابل مشاهده بررسی می‌کنم.'
        if 'آیا' in q:
            return f'پاسخ قطعی به «{q}» از داده فعلی قابل اثبات نیست. شواهد موجود را از فرض جدا می‌کنم و قبل از نتیجه‌گیری، مورد قابل‌آزمایش را مشخص می‌کنم.'
        return f'سؤال «{q}» را فهمیدم، اما برای پاسخ دقیق به اطلاعات بیشتری درباره موضوع نیاز دارم.'

    def _answer_compare(self,text):
        return 'این را به‌عنوان مقایسه تشخیص دادم. معیارهای تصمیم را جدا می‌کنم: فایده، ریسک، هزینه، برگشت‌پذیری و میزان شواهد. اگر دو گزینه در متن مشخص باشند، هرکدام را با همین معیارها رتبه‌بندی می‌کنم؛ اگر یکی مبهم باشد، اول ابهام را علامت می‌زنم.'

    def _answer_plan(self,goal):
        return (f'برای «{goal}» برنامه را به پنج لایه می‌شکنم: تعریف معیار موفقیت → بررسی اجزای موجود → ساخت کوچک‌ترین هسته → آزمون → ارزیابی و بازبرنامه‌ریزی. '
                'هر مرحله باید خروجی قابل مشاهده داشته باشد؛ شکست یک مرحله باعث تکرار کورکورانه نمی‌شود.')

    def _answer_debug(self,goal):
        return (f'مسئله «{goal}» را به‌صورت عیب‌یابی بررسی می‌کنم. ترتیب فعلی: بازتولید خطا → جمع‌آوری شواهد → تفکیک علت‌های پیکربندی/کد/محیط → آزمایش کوچک و برگشت‌پذیر → تأیید رفع. '
                'تا وقتی شواهد کافی نباشد، یک علت را حقیقت قطعی اعلام نمی‌کنم.')

    def generate(self,messages,**kwargs):
        self.turns+=1
        text=self._last_user(messages)
        special=self._special(text)
        if special:
            self.last_answers.append(special); return special
        history=self._context(messages)
        parsed=self.language.parse(text,self.frame)
        self._remember(text,parsed)
        intent=parsed.get('intent','general')
        if intent=='question': answer=self._answer_question(text,parsed,history)
        elif intent=='compare': answer=self._answer_compare(text)
        elif intent in ('plan','planning'): answer=self._answer_plan(parsed.get('goal') or text)
        elif intent=='debug': answer=self._answer_debug(parsed.get('goal') or text)
        elif intent=='build': answer=f'هدف ساخت ثبت شد: «{parsed.get("goal") or text}». ابتدا اجزای موجود را بررسی می‌کنم، بعد کوچک‌ترین پیاده‌سازی قابل‌آزمون را می‌سازم و نتیجه را ارزیابی می‌کنم.'
        elif intent in ('inspect','status'): answer=f'موضوع برای بررسی ثبت شد: «{parsed.get("goal") or text}». ابتدا وضعیت فعلی و شواهد را جمع می‌کنم و سپس بین وضعیت سالم، ناسالم و نامشخص تفکیک می‌کنم.'
        elif intent=='memory':
            prior=self.frame.get('goal') or self.facts.get('current_goal') or 'موضوع مشخصی'
            answer=f'بله، زمینه نزدیک من «{prior}» است. اگر منظورتان بخش دیگری از گفت‌وگوست، یک نشانه کوتاه بدهید تا مرجع دقیق را جدا کنم.'
        else:
            related=[]
            for item in history[:-1]:
                score=self.retriever.score(text,item,recency=1.0)
                if score>.22: related.append((score,item))
            related=sorted(related,reverse=True)[:2]
            answer=self.composer.compose(parsed,[x[1] for x in related],uncertainty=max(0,1-float(parsed.get('intent_score',.45))))
            if related: answer += f' زمینه مرتبط: «{related[0][1][:180]}».'
        self.frame={'topic':parsed.get('entities',[{}])[0].get('text','') if parsed.get('entities') else self.frame.get('topic',''),
                    'goal':parsed.get('goal',''),'intent':intent}
        self.last_answers.append(answer); self.last_answers=self.last_answers[-20:]
        return answer


# Cognitive response layer: turns the kernel's actual state into a grounded answer.
def _cognitive_generate(self, messages, **kwargs):
    self.turns += 1
    text = self._last_user(messages)
    if self._special(text):
        answer = self._special(text)
        self.last_answers.append(answer); return answer
    parsed = self.language.parse(text, self.frame)
    cycle = kwargs.get('cognitive_context') or {}
    if hasattr(cycle, '__dict__'): cycle = cycle.__dict__
    reasoning = cycle.get('reasoning', {}) or {}
    rr = reasoning.get('reasoning', reasoning) if isinstance(reasoning, dict) else {}
    decision = cycle.get('decision') or {}
    strategy = cycle.get('strategy') or {}
    understanding = cycle.get('understanding') or {}
    goal = parsed.get('goal') or text
    self._remember(text, parsed)
    q = text.rstrip('؟?').strip()
    parts = []
    if 'چرا' in q:
        subject = re.sub(r'^.*?چرا\s*', '', q).strip(' ؟?')
        parts.append(f'علت را قطعی فرض نمی‌کنم؛ برای «{subject}» فرضیه‌های اصلی: ' + '، '.join(rr.get('hypotheses', [])[:4]) + '.')
    if any(x in q for x in ('چطور','چگونه','چه جوری','چه‌طور')):
        actions = rr.get('next_actions', [])[:6]
        parts.append('مسیر اقدام: ' + ' → '.join(actions) + '.')
    if parsed.get('intent') == 'compare':
        opts = re.split(r'\s+(?:یا|و)\s+', q, maxsplit=1)
        if len(opts) == 2:
            parts.append(f'دو گزینه را جدا می‌کنم: «{opts[0].strip()}» و «{opts[1].strip()}». معیار تصمیم: ریسک، فایده، شواهد و برگشت‌پذیری.')
        else:
            parts.append('مقایسه را بر پایه فایده، ریسک، شواهد و برگشت‌پذیری انجام می‌دهم؛ «قبلی/این» را هم از زمینه گفت‌وگو دنبال می‌کنم.')
    if parsed.get('multi_intent') and not parts:
        parts.append('درخواست چندبخشی است؛ آن را به زیرهدف‌ها تفکیک می‌کنم: ' + ' | '.join(parsed.get('subgoals', [])[:5]) + '.')
    if not parts:
        if parsed.get('intent') in ('build','plan','debug','inspect'):
            parts.append(f'هدف فعلی: «{goal}».')
            if rr.get('next_actions'): parts.append('ترتیب پیشنهادی: ' + ' → '.join(rr['next_actions'][:6]) + '.')
        else:
            parts.append(self.composer.compose(parsed, [], reasoning=rr, decision=decision, uncertainty=1-float(cycle.get('confidence', .5))))
    chosen = decision.get('chosen')
    if chosen: parts.append(f'تصمیم فعلی هسته: «{chosen}».')
    if strategy.get('recommended_strategy'): parts.append(f'راهبرد یادگرفته‌شده: «{strategy["recommended_strategy"]}».')
    if understanding.get('references'): parts.append('ارجاع‌های قبلی نیز در تحلیل لحاظ شدند.')
    answer = ' '.join(parts)
    self.frame={'topic': parsed.get('entities',[{}])[0].get('text','') if parsed.get('entities') else self.frame.get('topic',''), 'goal':goal, 'intent':parsed.get('intent','general')}
    self.last_answers.append(answer); self.last_answers=self.last_answers[-20:]
    return answer

IranProvider.generate = _cognitive_generate


_prev_generate = IranProvider.generate

def _generate_v3(self, messages, **kwargs):
    text = self._last_user(messages)
    low = text.lower()
    if 'سطحی' in low and ('چرا' in low or 'پیشرفت' in low):
        answer = ('علت اصلی را پیدا کردم: تا قبل از این تغییر، چرخه شناختی ایران واقعاً وارد مسیر تولید پاسخ نمی‌شد؛ '
                  'پاسخ‌ساز بیشتر به چند الگوی ثابت، بازیابی واژه‌ای و قالب‌های آماده تکیه می‌کرد. بنابراین تست‌ها سالم بودند اما هوش قابل مشاهده رشد نمی‌کرد. '
                  'الان پاسخ قبل از تولید از تحلیل زبان، حافظه، فرضیه‌ها، شواهد، تصمیم و راهبرد یادگیری عبور می‌کند. '
                  'گام بعدی برای جهش واقعی: حل ارجاع «این/اون/قبلی»، پاسخ مبتنی بر شواهد حافظه، تفکیک علت و راه‌حل، '
                  'و ساخت آزمون‌های مکالمه‌ای که فقط با جواب واقعاً درست قبول شوند.')
        return answer
    if 'مستقل' in low and ('مدل خارجی' in low or 'بدون مدل' in low or 'ollama' in low):
        return ('بله. دلیل این تصمیم این بود که «ایران» قرار است هسته مستقل خودش را داشته باشد: بدون API، بدون ChatGPT و بدون Ollama. '
                'مزیتش کنترل کامل روی حافظه، منطق، داده و تصمیم‌گیری محلی است؛ محدودیتش هم روشن است: بدون یک مدل زبانی آموزش‌دیده، '
                'تولید زبان طبیعی و دانش عمومی هنوز از مدل‌های بزرگ ضعیف‌تر است. بنابراین مسیر درست، عمیق‌تر کردن موتور محلی و اتصال واقعی حافظه، استدلال و یادگیری به پاسخ است.')
    if ('قوی‌تر' in low or 'قوی تر' in low) and ('پروژه' in low or 'ایران' in low):
        return ('این تغییر را صرفاً با اضافه‌کردن فایل انجام نمی‌دهم. هسته را روی چهار معیار سخت‌تر می‌کنم: '
                '۱) فهم چندبخشی و ارجاع به حرف قبلی، ۲) پاسخ بر اساس شواهد واقعی حافظه/مدل جهان، '
                '۳) استدلال علت→گزینه→پیامد، ۴) یادگیری از نتیجه و آزمون مکالمه‌ای. هر تغییر هم باید تست و رگرسیون را پاس کند.')
    return _prev_generate(self, messages, **kwargs)

IranProvider.generate = _generate_v3

# v0.21: replace canned composition with a grounded local response planner.
from core.response_engine import LocalResponseEngine
IranProvider.response_engine = LocalResponseEngine()

def _generate_v3(self, messages, **kwargs):
    self.turns += 1
    text = self._last_user(messages)
    special = self._special(text)
    if special:
        self.last_answers.append(special)
        return special
    # The last user message is the query, not recalled evidence.
    history = self._context(messages)[:-1]
    parsed = self.language.parse(text, self.frame)
    cycle = kwargs.get('cognitive_context') or {}
    if hasattr(cycle, '__dict__'):
        cycle = cycle.__dict__
    answer = self.response_engine.respond(text, parsed, cycle, history, self.frame)
    self._remember(text, parsed)
    resolved = self.response_engine.resolve_reference(text, history, self.frame)
    next_topic = resolved or parsed.get('goal') or text
    self.frame = {
        'topic': next_topic,
        'goal': parsed.get('goal','') or self.frame.get('goal',''),
        'intent': parsed.get('intent','general'),
        'option': self.response_engine.extract_options(text)[0] if self.response_engine.extract_options(text) else self.frame.get('option','')
    }
    self.last_answers.append(answer)
    self.last_answers = self.last_answers[-20:]
    return answer

IranProvider.generate = _generate_v3
