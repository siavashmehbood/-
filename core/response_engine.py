import re
from collections import Counter

class LocalResponseEngine:
    """Deterministic Persian response planner: decomposes intent, grounds in context, and avoids canned filler."""
    FILLERS={'بگو','گفتیم','هست','است','را','رو','یه','این','آن','من','تو','ما','برای','درباره','میشه','می‌شود','لطفا','لطفاً'}
    REF={'این یکی':'last_option','همین پروژه':'project','موضوع قبلی':'last_topic','روش قبلی':'last_topic','مورد قبلی':'last_topic','همونو':'last_topic','همون رو':'last_topic','اون یکی':'last_option','این':'last_topic','همین':'last_topic','اون':'last_topic','آن':'last_topic','قبلی':'last_topic','بالایی':'last_topic'}
    WHY={'چرا','دلیل','علت','به چه دلیل'}
    HOW={'چطور','چگونه','چه‌طور','چه جوری','چجوری'}
    MEMORY={'یادت','یادته','یادت هست','قبلاً','قبلا','دیروز','هفته پیش','گفتیم','صحبت کردیم'}
    def clean(self,text):
        return re.sub(r'\s+',' ',str(text).strip().replace('ي','ی').replace('ك','ک'))
    def keywords(self,text):
        t=self.clean(text).lower()
        words=re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*',t)
        return [w for w in words if len(w)>2 and w not in self.FILLERS]
    def split_intents(self,text):
        t=self.clean(text).rstrip('؟?')
        chunks=re.split(r'\s*(?:و|ولی|اما|همچنین|؛|;|\.\s*)\s*',t)
        out=[]
        for c in chunks:
            if any(x in c for x in self.WHY): kind='why'
            elif any(x in c for x in self.HOW): kind='how'
            elif any(x in c for x in ('کدام','مقایسه','فرق','تفاوت','بهتره','بهتر است')): kind='compare'
            elif any(x in c for x in self.MEMORY): kind='memory'
            elif any(x in c for x in ('بساز','ساخت','پیاده','انجام','اجرا')): kind='action'
            else: kind='general'
            if c.strip(): out.append((kind,c.strip()))
        return out
    def context_hits(self,text,history,limit=4):
        q=set(self.keywords(text)); scored=[]
        for i,item in enumerate(history):
            s=str(item)
            k=set(self.keywords(s)); overlap=len(q&k)
            if overlap: scored.append((overlap/(len(q) or 1),i,s))
        return [x for x in sorted(scored,reverse=True)[:limit]]
    def resolve_reference(self,text,history,frame):
        t=self.clean(text)
        for marker,target in sorted(self.REF.items(),key=lambda x:-len(x[0])):
            if marker in t:
                if target=='last_topic': return frame.get('topic') or self._last_content(history)
                if target=='last_option': return frame.get('option') or self._last_content(history)
                if target=='project': return 'پروژه ایران'
        if any(marker in t for marker in ('ادامه بده','بیشتر توضیح بده','بیشتر بگو','ادامه‌اش','ادامه‌اش بده')):
            return frame.get('topic') or frame.get('goal') or self._last_content(history)
        return ''
    def _last_content(self,history):
        return str(history[-1]) if history else ''
    def extract_options(self,text):
        t=self.clean(text).rstrip('؟?')
        patterns=[r'بین (.+?) و (.+?)(?: کدام| بهتر|$)',r'(.+?) یا (.+?)(?: بهتر| خوب|$)',r'مقایسه(?:‌ی| ی)? (.+?) و (.+)$']
        for p in patterns:
            m=re.search(p,t)
            if m:
                a,b=m.group(1).strip(' ،.'),m.group(2).strip(' ،.')
                return [a,b]
        return []
    def constraints(self,text):
        t=self.clean(text); out=[]
        for marker in ('بدون','نباید','فقط','حتماً','حداقل','حداکثر','ترجیحاً','فعلاً'):
            m=re.search(rf'{re.escape(marker)}\s+([^،؛.]+)',t)
            if m: out.append(f'{marker} {m.group(1).strip()}')
        return out
    def why(self,text,cycle,history):
        q=self.clean(text).rstrip('؟?')
        subject=re.sub(r'^.*?چرا\s*','',q).strip() or q
        rr=(cycle.get('reasoning') or {}).get('reasoning',{})
        hypotheses=rr.get('hypotheses',[])[:4]
        hits=self.context_hits(text,history)
        specific=[]
        low=q.lower()
        if any(x in low for x in ('سطحی','جواب','پاسخ','هوشمند','درک زبان')):
            specific.append('علت اصلی در وضعیت فعلی این است که موتور پاسخ‌گویی محلی هنوز مولد عصبی نیست؛ بخش زبانی بیشتر نمادین، قاعده‌محور و بازیابی‌محور است.')
            specific.append('یعنی هسته می‌تواند نیت، حافظه، فرضیه و تصمیم بسازد، اما تبدیل این وضعیت به متن طبیعی و استدلال چندمرحله‌ای هنوز گلوگاه است.')
        elif 'کند' in low:
            specific.append('در اجرای فعلی یک گلوگاه واقعی هم وجود داشت: چرخه شناختی در مسیر پاسخ دوباره اجرا می‌شد؛ این هم زمان را بالا می‌برد و هم داده تکراری وارد حافظه می‌کرد.')
        if not specific:
            specific.append(f'برای «{subject}» از داده فعلی علت قطعی ندارم؛ به‌جای حدس واحد، علت‌ها را به چند فرضیه رقیب تقسیم می‌کنم.')
        if hypotheses:
            specific.append('فرضیه‌های هسته: ' + '، '.join(hypotheses) + '.')
        if hits:
            evidence=hits[0][2][:180].replace('\n',' ')
            specific.append(f'نزدیک‌ترین شاهد محلی: «{evidence}».')
        return ' '.join(specific)
    def how(self,text,cycle):
        rr=(cycle.get('reasoning') or {}).get('reasoning',{})
        actions=rr.get('next_actions',[])[:5]
        q=self.clean(text).rstrip('؟?')
        subject=re.sub(r'^.*?(چطور|چگونه|چه‌طور|چه جوری|چجوری)\s*','',q).strip() or q
        if any(x in q for x in ('بهترش','بهترش کنیم','سطحی','هوشمندتر')):
            actions=['تجزیه سؤال به زیرمسئله‌ها','بازیابی شواهد مرتبط به‌جای متن خام حافظه','حل هر زیرمسئله با فرضیه‌های رقیب','ترکیب نتیجه‌ها در یک پاسخ منسجم','ثبت خطا و استفاده از آن در پاسخ بعدی']
        if not actions: actions=['تعریف هدف و معیار موفقیت','بازیابی زمینه مرتبط','ساخت چند فرضیه','انتخاب کم‌ریسک‌ترین اقدام','آزمون نتیجه و بازنگری']
        return f'برای «{subject}» مسیر عملی این است: ' + ' → '.join(actions) + '.'
    def compare(self,text,cycle):
        opts=self.extract_options(text)
        if not opts: return 'دو گزینه روشن در متن پیدا نکردم؛ معیارهای مقایسه را از خود سؤال استخراج می‌کنم و ابهام را نگه می‌دارم.'
        a,b=opts
        low=(a+' '+b).lower()
        if 'حافظه' in low:
            rows=[('بازیابی گفت‌وگو','قوی‌تر برای ادامه همان بحث','بهتر برای یافتن مفهوم مشابه در بحث‌های قدیمی'),('معنایی','ضعیف‌تر بدون مدل برداری قوی','قوی‌تر برای شباهت مفهومی'),('دقت مرجع','بالا وقتی ترتیب گفتگو حفظ شود','متوسط؛ ممکن است متن مشابه ولی نامرتبط را برگرداند')]
            return f'بین «{a}» و «{b}»، انتخاب مطلق نداریم. برای گفت‌وگوی جاری، حافظه رویدادی/ترتیبی بهتر است؛ برای یافتن مفهوم مشابه، حافظه معنایی بهتر است. معماری درست ترکیب هر دو است. ' + '؛ '.join(f'{x}: {y}' for x,y,z in rows)
        return f'«{a}» و «{b}» را با چهار معیار می‌سنجم: فایده، ریسک، هزینه و برگشت‌پذیری. بدون داده کافی برنده قطعی اعلام نمی‌کنم؛ اول معیار غالب سؤال را مشخص می‌کنم.'
    def memory_answer(self,text,history,frame):
        hits=self.context_hits(text,history,6)
        if not hits:
            return 'از حافظه فعلی شاهد کافی برای این مرجع پیدا نکردم؛ نمی‌خواهم چیزی را به‌عنوان خاطره قطعی بسازم.'
        lines=[]
        for score,idx,item in hits[:3]:
            s=self.clean(item)
            if len(s)>220: s=s[:220]+'…'
            lines.append(s)
        return 'برای این مرجع، نزدیک‌ترین قطعات ذخیره‌شده این‌ها هستند:\n' + '\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    def action_answer(self,text,cycle):
        c=self.constraints(text)
        rr=(cycle.get('reasoning') or {}).get('reasoning',{})
        actions=rr.get('next_actions',[])[:5] or ['بررسی اجزای موجود','ساخت تغییر کوچک','اجرای تست','ثبت نتیجه']
        base='برای اجرای این درخواست، اول پیش‌شرط‌ها را مشخص می‌کنم و بعد تغییر را مرحله‌ای انجام می‌دهم. '
        if c: base += 'محدودیت‌ها: ' + '؛ '.join(c) + '. '
        return base+'گام‌ها: '+' → '.join(actions)+'.'
    def general(self,text,parsed,history,frame):
        hits=self.context_hits(text,history,2)
        ref=self.resolve_reference(text,history,frame)
        if ref:
            return f'مرجع «{text.strip()}» را به «{self.clean(ref)[:160]}» وصل کردم. حالا همین موضوع را مبنای پاسخ قرار می‌دهم.'
        if hits:
            return f'برداشت من این است که موضوع «{self.clean(text).rstrip("؟?")}» به زمینه قبلی وصل است. نزدیک‌ترین زمینه: «{self.clean(hits[0][2])[:180]}». بر همان مبنا ادامه می‌دهم.'
        if parsed.get('intent') == 'question' or self.clean(text).endswith(('؟','?')):
            return ('UNKNOWN: برای این سؤال در حافظه، دانش و شواهد محلی پاسخ قابل اتکایی ندارم. '
                    'اگر داده یا منبع مجاز مشخصی بدهی، دوباره بررسی و نتیجه را با سطح اطمینان اعلام می‌کنم.')
        return f'موضوع را به‌عنوان «{self.clean(text).rstrip("؟?")}» ثبت کردم. برای اینکه پاسخ فقط تکرار سؤال نباشد، هدف، شواهد موجود و نتیجه قابل‌آزمایش را از هم جدا می‌کنم.'
    def respond(self,text,parsed,cycle,history,frame):
        kinds=self.split_intents(text)
        parts=[]
        seen=set()
        for kind,chunk in kinds:
            if kind in seen: continue
            seen.add(kind)
            if kind=='why': parts.append(self.why(chunk,cycle,history))
            elif kind=='how': parts.append(self.how(chunk,cycle))
            elif kind=='compare': parts.append(self.compare(chunk,cycle))
            elif kind=='memory': parts.append(self.memory_answer(chunk,history,frame))
            elif kind=='action': parts.append(self.action_answer(chunk,cycle))
        if not parts: parts.append(self.general(text,parsed,history,frame))
        confidence=float(cycle.get('confidence',parsed.get('confidence',.5)) or .5)
        if confidence<.35: parts.append('اطمینان این برداشت پایین است؛ اگر داده بیشتری وارد شود، پاسخ را بازبینی می‌کنم.')
        return '\n\n'.join(parts)

# Compatibility: action responses expose the extracted goal explicitly.
def _action_v2(self,text,cycle):
    c=self.constraints(text)
    goal=self.clean(text)
    rr=(cycle.get('reasoning') or {}).get('reasoning',{})
    actions=rr.get('next_actions',[])[:5] or ['بررسی اجزای موجود','ساخت تغییر کوچک','اجرای تست','ثبت نتیجه']
    out=f'هدف: «{goal}». ابتدا پیش‌شرط‌ها را مشخص می‌کنم و بعد تغییر را مرحله‌ای انجام می‌دهم. '
    if c: out += 'محدودیت‌ها: ' + '؛ '.join(c) + '. '
    return out+'گام‌ها: '+' → '.join(actions)+'.'
LocalResponseEngine.action_answer = _action_v2

# v0.22: evidence-grounded response layer. This is the main visible intelligence upgrade.
def _compact(self,text,n=240):
    s=self.clean(text).replace('Relevant memory:','').strip()
    return s if len(s)<=n else s[:n]+'…'

def _cycle_parts(self,cycle):
    cycle=cycle or {}
    rr=cycle.get('reasoning',{}) if isinstance(cycle,dict) else {}
    if isinstance(rr,dict): rr=rr.get('reasoning',rr)
    return rr or {}, cycle.get('decision') or {}, cycle.get('predictions') or [], cycle.get('strategy') or {}, cycle.get('reflection') or {}

def _evidence_lines(self,cycle,history,limit=4):
    rr,_,_,_,_=self._cycle_parts(cycle); out=[]
    for x in rr.get('evidence',[])[:limit]:
        s=self._compact(x)
        if s and s not in out: out.append(s)
    if not out:
        for _,_,s in self.context_hits('',history,0):
            out.append(self._compact(s))
    return out[:limit]

LocalResponseEngine._compact=_compact
LocalResponseEngine._cycle_parts=_cycle_parts
LocalResponseEngine._evidence_lines=_evidence_lines

def _why_v2(self,text,cycle,history):
    q=self.clean(text).rstrip('؟?'); subject=re.sub(r'^.*?چرا\s*','',q).strip() or q
    rr,decision,preds,strategy,_=self._cycle_parts(cycle); hy=rr.get('hypotheses',[])[:4]
    evidence=self._evidence_lines(cycle,history,3)
    low=q.lower(); parts=[]
    if any(x in low for x in ('سطحی','جواب','پاسخ','هوشمند','درک زبان')):
        parts.append('گلوگاه اصلی «تولید زبان و ترکیب استدلال» است؛ هسته شناختی داده ساختاری می‌سازد اما موتور محلی هنوز مدل مولد عصبی ندارد.')
        parts.append('در نتیجه ممکن است تحلیل داخلی درست‌تر از چیزی باشد که متن نهایی نشان می‌دهد؛ این دقیقاً بخشی است که اکنون داریم از هم جدا می‌کنیم.')
    elif 'کند' in low:
        parts.append('کندی فقط یک حدس نیست: چرخه شناختی قبلاً دوبار در هر نوبت اجرا می‌شد و این باعث محاسبه و ثبت تکراری می‌شد؛ این مسیر اصلاح شده است.')
        parts.append('بعد از آن، بازیابی حافظه و تولید پاسخ باید سبک‌تر شود؛ سرعت واقعی با اندازه‌گیری زمان هر مرحله سنجیده می‌شود.')
    elif hy:
        parts.append('برای این سؤال یک علت واحد را قطعی نمی‌کنم؛ فرضیه‌های رقیب عبارت‌اند از: '+ '، '.join(hy)+'.')
    else: parts.append(f'برای «{subject}» شاهد کافی برای علت قطعی ندارم.')
    if evidence: parts.append('شاهدهای محلی: ' + ' | '.join(f'«{x}»' for x in evidence))
    if decision.get('chosen'): parts.append(f'تصمیم فعلی هسته: «{decision["chosen"]}».')
    if strategy.get('recommended_strategy'): parts.append(f'راهبرد انتخاب‌شده: «{strategy["recommended_strategy"]}».')
    return ' '.join(parts)


def _how_v2(self,text,cycle):
    q=self.clean(text).rstrip('؟?'); subject=re.sub(r'^.*?(چطور|چگونه|چه‌طور|چه جوری|چجوری)\s*','',q).strip() or q
    rr,decision,preds,strategy,_=self._cycle_parts(cycle); actions=rr.get('next_actions',[])[:7]
    if any(x in q for x in ('بهتر','قوی','هوشمند','سطحی')):
        actions=['تقویت درک چندبخشی و ارجاع به مکالمه','بازیابی معنایی و زمانی از حافظه','استدلال چندفرضیه‌ای با شواهد مثبت و منفی','تبدیل تصمیم و پیامد به متن طبیعی','ثبت نتیجه و کالیبراسیون پیش‌بینی','اجرای رگرسیون مکالمه‌ای']
    if not actions: actions=['تعریف هدف','بازیابی زمینه','ساخت فرضیه','مقایسه گزینه‌ها','اقدام کم‌ریسک','مشاهده نتیجه','یادگیری']
    out=f'برای «{subject}» مسیر عملی: '+' → '.join(actions)+'.'
    if preds:
        best=preds[0]; out+=f' اولویت فعلی: «{best.get("action","") if isinstance(best,dict) else getattr(best,"action","") }».'
    return out

LocalResponseEngine.why=_why_v2
LocalResponseEngine.how=_how_v2

def _compare_v2(self,text,cycle):
    opts=self.extract_options(text)
    if len(opts)<2:
        return 'مقایسه ناقص است؛ دو گزینه صریح پیدا نشدند. «این/قبلی» را از زمینه مکالمه نگه می‌دارم و برنده ساختگی اعلام نمی‌کنم.'
    a,b=opts; rr,decision,preds,strategy,_=self._cycle_parts(cycle)
    criteria=['فایده','ریسک','هزینه','برگشت‌پذیری','شواهد موجود']
    return (f'مقایسه «{a}» با «{b}»: معیارها = '+ '، '.join(criteria)+'. '
            f'در وضعیت فعلی، بدون داده اختصاصی برای این دو گزینه برنده قطعی نمی‌سازم. '
            f'تصمیم‌گیر هسته فعلاً «{decision.get("chosen","جمع‌آوری شواهد") if isinstance(decision,dict) else "جمع‌آوری شواهد"}» را ترجیح داده است.')


def _memory_v2(self,text,history,frame):
    hits=self.context_hits(text,history,8)
    if not hits:
        return 'در حافظه محلی شاهد کافی برای این ارجاع پیدا نکردم؛ خاطره ساختگی تولید نمی‌کنم.'
    lines=[]; seen=set()
    for score,idx,item in hits:
        s=self._compact(item,260)
        if s not in seen: seen.add(s); lines.append(f'{len(lines)+1}. {s} (ارتباط {score:.2f})')
        if len(lines)>=4: break
    return 'نزدیک‌ترین خاطرات مرتبط، با رتبه‌بندی ارتباطی:\n'+'\n'.join(lines)


def _action_v2b(self,text,cycle):
    c=self.constraints(text); rr,decision,preds,strategy,_=self._cycle_parts(cycle)
    goal=self.clean(text); actions=rr.get('next_actions',[])[:7] or ['بررسی اجزای موجود','اجرای تغییر کوچک','تست','ارزیابی']
    out=f'هدف: «{goal}». '
    if c: out+='محدودیت‌ها: '+'؛ '.join(c)+'. '
    out+='برنامه اجرایی: '+' → '.join(actions)+'. '
    if decision.get('chosen'): out+=f'اولین اقدام انتخاب‌شده: «{decision["chosen"]}». '
    if strategy.get('recommended_strategy'): out+=f'راهبرد: «{strategy["recommended_strategy"]}». '
    return out

LocalResponseEngine.compare=_compare_v2
LocalResponseEngine.memory_answer=_memory_v2
LocalResponseEngine.action_answer=_action_v2b

# v0.22b: unwrap nested evidence produced by EvidenceReasoner.
def _evidence_lines_v2(self,cycle,history,limit=4):
    rr,_,_,_,_=self._cycle_parts(cycle); out=[]
    inf=rr.get('evidence_inference',{}) if isinstance(rr,dict) else {}
    for h in inf.get('hypotheses',[]) if isinstance(inf,dict) else []:
        for e in h.get('evidence',[]) if isinstance(h,dict) else []:
            s=self._compact(e.get('text','') if isinstance(e,dict) else e)
            if s and s not in out: out.append(s)
            if len(out)>=limit:return out
    return out
LocalResponseEngine._evidence_lines=_evidence_lines_v2

# v0.22c: protect semantic spans before conjunction splitting.
def _split_intents_v2(self,text):
    t=self.clean(text).rstrip('؟?')
    if ('بین ' in t and ' و ' in t and any(x in t for x in ('کدام','بهتر','مقایسه'))): return [('compare',t)]
    if ('چرا' in t and any(x in t for x in self.HOW)):
        m=re.search(r'\s+و\s+(?=(چطور|چگونه|چه جوری|چجوری|چه‌طور))',t)
        if m:return [('why',t[:m.start()].strip()),('how',t[m.end():].strip())]
    chunks=re.split(r'\s*(?:و|ولی|اما|همچنین|؛|;|\.\s*)\s*',t)
    out=[]
    for c in chunks:
        if any(x in c for x in self.WHY): kind='why'
        elif any(x in c for x in self.HOW): kind='how'
        elif any(x in c for x in ('کدام','مقایسه','فرق','تفاوت','بهتره','بهتر است')): kind='compare'
        elif any(x in c for x in self.MEMORY): kind='memory'
        elif any(x in c for x in ('بساز','ساخت','پیاده','انجام','اجرا')): kind='action'
        else: kind='general'
        if c.strip():out.append((kind,c.strip()))
    return out
LocalResponseEngine.split_intents=_split_intents_v2

# v0.22d: memory answers must not cite the current question as a recalled memory.
def _memory_v3(self,text,history,frame):
    past=list(history[:-1]) if history else []
    hits=self.context_hits(text,past,10)
    if not hits:return 'در حافظه محلی شاهد کافی برای این ارجاع پیدا نکردم؛ خاطره ساختگی تولید نمی‌کنم.'
    lines=[];seen=set(); current=self.clean(text)
    for score,idx,item in hits:
        s=self._compact(item,260)
        if not s or s==current or s in seen or s.startswith('برای این مرجع،'):continue
        seen.add(s);lines.append(f'{len(lines)+1}. {s} (ارتباط {score:.2f})')
        if len(lines)>=4:break
    return 'نزدیک‌ترین خاطرات مرتبط، با رتبه‌بندی ارتباطی:\n'+'\n'.join(lines) if lines else 'در حافظه محلی شاهد مستقل کافی پیدا نکردم.'
LocalResponseEngine.memory_answer=_memory_v3

_old_action_split=_split_intents_v2
def _split_intents_v3(self,text):
    t=self.clean(text).rstrip('؟?')
    if any(x in t for x in ('بساز','پیاده','اجرا کن','انجام بده')) and any(x in t for x in ('بدون','نباید','فقط','حتماً','با تست')):
        return [('action',t)]
    return _old_action_split(self,t)
LocalResponseEngine.split_intents=_split_intents_v3

# v0.23: semantic grounding and Persian execution language.
def _memory_v4(self,text,history,frame):
    hits=self.context_hits(text,list(history[:-1]) if history else [],10); rows=[]
    cycle=getattr(self,'_active_cycle',{}) or {}
    sm=cycle.get('semantic_memory',{}) if isinstance(cycle,dict) else {}
    for h in hits[:3]: rows.append(self._compact(h[2],230))
    facts=sm.get('matches',[]) if isinstance(sm,dict) else []
    for f in facts[:3]:
        s=f'{f.get("subject")} ← {f.get("predicate")} → {f.get("value")} (اطمینان {float(f.get("confidence",0)):.2f})'
        if s not in rows: rows.append(s)
    if not rows:return 'در حافظه محلی و معنایی شاهد کافی برای این ارجاع پیدا نکردم؛ خاطره ساختگی تولید نمی‌کنم.'
    return 'حافظه مرتبط:\n'+'\n'.join(f'{i+1}. {x}' for i,x in enumerate(rows[:5]))
LocalResponseEngine.memory_answer=_memory_v4

def _action_v3(self,text,cycle):
    c=self.constraints(text); rr,decision,preds,strategy,_=self._cycle_parts(cycle)
    plan=['فهم هدف و محدودیت‌ها','بررسی شواهد و اجزای موجود','انتخاب کوچک‌ترین اقدام برگشت‌پذیر','اجرای آزمون و مشاهده نتیجه','ثبت نتیجه و بازبرنامه‌ریزی']
    out=f'هدف اجرایی: «{self.clean(text)}». '
    if c: out+='محدودیت‌ها: '+'؛ '.join(c)+'. '
    out+='برنامه: '+' → '.join(plan)+'. '
    if decision.get('chosen'): out+=f'تصمیم هسته: «{decision["chosen"]}». '
    if strategy.get('recommended_strategy'): out+=f'راهبرد: «{strategy["recommended_strategy"]}». '
    return out
LocalResponseEngine.action_answer=_action_v3

_old_respond_engine=LocalResponseEngine.respond
def _respond_v2(self,text,parsed,cycle,history,frame):
    self._active_cycle=cycle or {}
    try:return _old_respond_engine(self,text,parsed,cycle,history,frame)
    finally:self._active_cycle={}
LocalResponseEngine.respond=_respond_v2

# v0.24: temporal episodic evidence outranks generic lexical memory for memory questions.
_old_memory_answer = LocalResponseEngine.memory_answer

def _memory_answer_v2(self,text,history,frame):
    cycle = getattr(self, '_active_cycle', {}) or {}
    episodic = cycle.get('understanding', {}).get('episodic', {}) if isinstance(cycle, dict) else {}
    episodes = episodic.get('episodes', []) if isinstance(episodic, dict) else []
    if episodes:
        lines=[]
        for item in episodes[:4]:
            content=self.clean(item.get('content',''))
            if content and content not in lines:
                lines.append(content[:240])
        if lines:
            temporal=episodic.get('temporal')
            prefix=f'در حافظه زمانی «{temporal}» ' if temporal else 'در حافظه زمانی '
            return prefix+'این موارد ثبت شده‌اند:\n'+'\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return _old_memory_answer(self,text,history,frame)

LocalResponseEngine.memory_answer = _memory_answer_v2


# v0.30: dialogue recall prioritizes real user/assistant turns over internal telemetry.
def _memory_answer_v30(self,text,history,frame):
    cycle=getattr(self,'_active_cycle',{}) or {}
    episodic=cycle.get('understanding',{}).get('episodic',{}) if isinstance(cycle,dict) else {}
    episodes=episodic.get('episodes',[]) if isinstance(episodic,dict) else []
    query=self.clean(text).rstrip('؟?')
    generic=any(x in query for x in ('یادت هست من چی گفتم','چی گفتم قبلا','چی گفتم قبلاً','حرف قبلی','حرفم چی بود'))
    allowed={'user','assistant','fact','goal','lesson'}
    if generic:
        rows=[x for x in episodes if x.get('kind') in allowed]
        users=[x for x in rows if x.get('kind')=='user' and self.clean(x.get('content',''))!=query]
        if users:
            return 'آخرین چیزی که از حرف‌های خودت ثبت شده:\n'+'\n'.join(f'{i+1}. {self._compact(x.get("content",""),260)}' for i,x in enumerate(users[:4]))
    rows=[x for x in episodes if x.get('kind') in allowed]
    if rows:
        lines=[];seen=set()
        for x in rows:
            content=self._compact(x.get('content',''),260)
            if not content or content==query or content in seen: continue
            seen.add(content); lines.append(content)
            if len(lines)>=4: break
        if lines:
            temporal=episodic.get('temporal')
            prefix=f'در حافظه زمانی «{temporal}» ' if temporal else 'در حافظه گفتگو '
            return prefix+'این موارد ثبت شده‌اند:\n'+'\n'.join(f'{i+1}. {x}' for i,x in enumerate(lines))
    return 'در حافظه محلی شاهد مستقل کافی برای این مرجع پیدا نکردم.'

LocalResponseEngine.memory_answer=_memory_answer_v30


# v0.33: conjunction splitting is token-boundary safe; never split inside Persian words such as «چطور».
def _split_intents_safe(self, text):
    t=self.clean(text).rstrip('؟?')
    if ('بین ' in t and ' و ' in t and any(x in t for x in ('کدام','بهتر','مقایسه'))):
        return [('compare',t)]
    chunks=re.split(r'\s*(?<![آ-یA-Za-z0-9‌])و(?![آ-یA-Za-z0-9‌])\s*|\s*(?:ولی|اما|همچنین|؛|;|\.\s*)\s*',t)
    out=[]
    for c in chunks:
        c=c.strip()
        if not c: continue
        if any(x in c for x in self.WHY): kind='why'
        elif any(x in c for x in self.HOW): kind='how'
        elif any(x in c for x in ('کدام','مقایسه','فرق','تفاوت','بهتره','بهتر است')): kind='compare'
        elif any(x in c for x in self.MEMORY): kind='memory'
        elif any(x in c for x in ('بساز','ساخت','پیاده','انجام','اجرا')): kind='action'
        else: kind='general'
        out.append((kind,c))
    return out
LocalResponseEngine.split_intents=_split_intents_safe


# v0.34: reference resolution and contextual recall operate on semantic turn content, not tuple representations.
def _resolve_reference_safe(self, text, history, frame):
    t=self.clean(text)
    markers=sorted(self.REF.items(), key=lambda x:-len(x[0]))
    for marker,target in markers:
        if re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])',t):
            if target=='last_topic': return str(frame.get('topic') or frame.get('goal') or self._last_content(history))
            if target=='last_option': return str(frame.get('option') or self._last_content(history))
            if target=='previous': return str(history[-2] if len(history)>1 else self._last_content(history))
            if target=='project': return 'پروژه ایران'
    return ''
LocalResponseEngine.resolve_reference=_resolve_reference_safe

def _context_hits_safe(self, text, history, limit=4):
    q=set(self.keywords(text)); q-=set(self.FILLERS)
    if not q: return []
    scored=[]
    for i,item in enumerate(history):
        s=self.clean(item if isinstance(item,str) else (item[1] if isinstance(item,(tuple,list)) and len(item)>1 else item))
        k=set(self.keywords(s)); k-=set(self.FILLERS); overlap=len(q&k)
        required=1 if len(q)<=2 else 2
        if overlap>=required:
            scored.append((overlap/max(1,len(q)),i,s))
    return sorted(scored,key=lambda x:(x[0],x[1]),reverse=True)[:limit]
LocalResponseEngine.context_hits=_context_hits_safe


# v0.34b: normalize history items at the final reference boundary.
def _last_content_safe(self, history):
    if not history: return ''
    item=history[-1]
    if isinstance(item,(tuple,list)) and len(item)>1: return str(item[1])
    return str(item)
LocalResponseEngine._last_content=_last_content_safe

def _resolve_reference_safe_v2(self, text, history, frame):
    t=self.clean(text)
    for marker,target in sorted(self.REF.items(), key=lambda x:-len(x[0])):
        if re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])',t):
            if target in ('last_topic','last_option'): return str(frame.get('goal') or frame.get('topic') or self._last_content(history))
            if target=='previous': return self._last_content(history)
            if target=='project': return 'پروژه ایران'
    return ''
LocalResponseEngine.resolve_reference=_resolve_reference_safe_v2


# v0.34c: compound references such as «همون قبلی» resolve as one phrase.
def _resolve_reference_safe_v3(self, text, history, frame):
    t=self.clean(text)
    if any(re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(p)}(?![آ-یA-Za-z0-9‌])',t) for p in ('همون قبلی','همون قبلیش','همونو')):
        return str(frame.get('goal') or frame.get('topic') or self._last_content(history))
    return _resolve_reference_safe_v2(self,text,history,frame)
LocalResponseEngine.resolve_reference=_resolve_reference_safe_v3
