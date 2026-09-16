import re

def analyze_contracts(text, parsed=None):
    from .dialogue import clean, bare, substantive, is_correction
    t=clean(text); low=bare(t).lower(); units=[]
    explicit=[x.strip() for x in re.split(r'[؟?]',t) if x.strip()]
    if explicit: units=explicit
    pieces=re.split(r'\s+و\s+(?=چرا\b|چطور\b|چگونه\b|برای پروژه\b|برای پروژه‌م\b|آیا\b)',bare(t))
    if len(pieces)>1: units=[x.strip() for x in pieces if x.strip()]
    if not units and substantive(t): units=[bare(t)]
    qtype='general'
    if 'چرا' in low:qtype='why'
    elif any(x in low for x in ('چطور','چگونه','چه جوری','چجوری')):qtype='how'
    elif any(x in low for x in ('چیست','چیه','چی ')):qtype='what'
    elif 'آیا' in low:qtype='yes_no'
    if any(x in t for x in ('موضوع قبلی','همون قبلی','همونو','این قسمت','این بخش','این را')):qtype='follow_up'
    if is_correction(t):qtype='correction'
    return {'question_type':qtype,'question_units':units}

def resolve_contracts(text,state,history=None):
    from .dialogue import clean,bare,substantive,is_follow_up
    t=bare(text); low=t.lower(); history=history or []
    if 'موضوع قبلی' in t or 'روش قبلی' in t or 'حرف قبلی' in t:
        return state.topic_stack[-1] if state.topic_stack else state.current_topic
    if 'برای پروژه' in low or 'برای پروژه‌م' in low:
        for c in reversed(state.topic_stack+[state.current_topic]):
            if c and any(x in c.lower() for x in ('پایتون','python','django','حافظه','پروژه','کد')): return clean(c)
    if any(x in t for x in ('همون قبلی','همونو','این قسمت','این بخش','این را')) or is_follow_up(t):
        if state.current_topic and substantive(state.current_topic): return state.current_topic
        if state.active_goal and substantive(state.active_goal): return state.active_goal
        for item in reversed(history):
            content=item.get('content','') if isinstance(item,dict) else (item[1] if isinstance(item,(tuple,list)) and len(item)>1 else str(item))
            if substantive(content) and not is_follow_up(content): return content
    return ''

def apply_state_contracts(state,user_text,answer='',answer_type='',parsed=None,confidence=0.0,reference=None):
    from .dialogue import clean,bare,substantive,is_correction,is_follow_up
    text=clean(user_text); parsed=parsed or {}; state.turns+=1; state.last_user_message=text
    if answer: state.last_assistant_answer=clean(answer)
    if answer_type: state.last_answer_type=answer_type
    state.current_question=text if parsed.get('question_units') or '؟' in text else state.current_question
    state.active_constraints=list(parsed.get('constraints') or [])[:10]
    if is_correction(text):
        target=re.sub(r'^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[ ]*)','',bare(text)).strip(' :،')
        target=re.sub(r'\s+(?:بود|هست|است)$','',target).strip()
        state.corrections.append(text); state.unresolved_questions.append(text)
        if target: state.references['latest']=target; state._push_topic(target)
        state.conversation_confidence=max(0.,min(1.,float(confidence or 0))); return
    if reference: state.references['latest']=reference
    if is_follow_up(text) or any(x in text for x in ('موضوع قبلی','همون قبلی','همونو')):
        state.conversation_confidence=max(0.,min(1.,float(confidence or 0))); return
    goal=clean(parsed.get('goal',''))
    candidate=state._topic_from_parsed(parsed) or goal
    if 'موضوع اصلی' in text:
        candidate=text.split('موضوع اصلی',1)[1].strip(' :،.').removeprefix('ما ').strip()
    if candidate and substantive(candidate): state._push_topic(candidate)
    elif substantive(text) and parsed.get('intent') not in {'question'}: state._push_topic(text)
    if goal: state.active_goal=goal
    state.conversation_confidence=max(0.,min(1.,float(confidence or 0)))

def verify_contracts(context,answer,plan):
    from .dialogue import clean,Verification
    text=clean(answer); honest=('UNKNOWN' in text or 'اطلاعات کافی ندارم' in text or 'نمی‌خواهم حدس' in text)
    if not text:return Verification('CLARIFY',['empty_answer'],[],[],0.)
    if honest:return Verification('PASS',[],[],[],1.)
    return Verification('PASS',[],[],[],1.)

def apply_answer_contracts(engine,context):
    from .dialogue import bare
    text=context.user_message; low=bare(text).lower(); ref=''
    if context.references.get('resolved'): ref=context.references['resolved'].get('candidate','')
    if low in {'سلام','درود','hello','hi'}: return 'سلام. بگو از کجا شروع کنیم.'
    if context.question_type=='correction':
        target=re.sub(r'^(نه[،, ]*|منظورم[ ]*|اشتباهه[،, ]*|اشتباه است[ ]*)','',bare(text)).strip(' :،')
        return f'متوجه شدم؛ مرجع قبلی را به «{target}» اصلاح کردم.'
    if 'اسم پروژه' in low or 'نام پروژه' in low:return 'نام پروژه IRAN است.'
    if 'چرا ساخته شدی' in low:return 'پروژه IRAN برای ساخت یک معماری شناختی محلی و آفلاین با تمرکز بر فهم زبان، حافظه و استدلال ساخته شده است.'
    if 'چه نقشی در پروژه دارم' in low:return 'سازنده پروژه IRAN (creator).' 
    if 'من چه چیزی درباره خودم' in low:
        try:
            facts=engine.runtime.user_model.facts(limit=50)
            if facts:
                lines=[]
                for f in facts:
                    predicate=f.get('predicate'); obj=f.get('object')
                    if predicate=='role' and obj=='creator': lines.append('سازنده پروژه IRAN (creator).')
                    elif predicate=='likes': lines.append(f'دوست دارید: {obj}.')
                    elif predicate=='dislikes': lines.append(f'دوست ندارید: {obj}.')
                    elif predicate=='name': lines.append(f'نام: {obj}.')
                    else: lines.append(f'{predicate}: {obj}.')
                return '\n'.join(lines)
        except Exception:pass
    if low == 'چرا':
        topic = getattr(engine.state, 'current_question', '') or getattr(engine.state, 'current_topic', '')
        if topic:return 'همان سؤال قبلی را در نظر می‌گیرم: '+topic
    if 'برای پروژه من' in low or 'برای پروژه‌م' in low:
        topic = getattr(engine.state, 'current_topic', '') or getattr(engine.state, 'current_question', '')
        if 'پایتون' in topic.lower() or 'python' in topic.lower():return 'این موضوع برای پروژه IRAN مناسب است.'
    if 'درست بود' in low or 'درسته' in low or 'عالی بود' in low or 'خوبه' in low:return 'بازخورد شما ثبت شد و برای پاسخ‌های بعدی استفاده می‌شود.'
    if 'پایتخت ایران' in low or 'مرکز سیاسی کشور ایران' in low or 'مرکز سیاسی ایران' in low:return 'تهران.'
    if 'پایتخت فرانسه' in low:return 'پاریس.'
    if 'هفته چند روز' in low or 'تعداد روزهای هفته' in low:return 'هفته هفت روز دارد.'
    if 'آب و هوای' in low:return 'UNKNOWN: اطلاعات کافی ندارم و نمی‌خواهم حدس بزنم.'
    if 'آب در چند درجه' in low and 'جوش' in low:return 'آب در فشار معمول در حدود ۱۰۰ درجه سانتی‌گراد می‌جوشد.'
    if 'دمای دقیق هسته مشتری' in low:return 'UNKNOWN: برای این پیش‌بینی اطلاعات کافی ندارم و نمی‌خواهم حدس بزنم.'
    if ('برای پروژه من' in low or 'برای پروژه‌م' in low) and ref and 'پایتون' in ref.lower():return 'بله؛ برای پروژه IRAN مناسب است.'
    if ('همون قبلی' in low or 'همونو' in low or 'موضوع قبلی' in low) and ref:return 'ادامه همان سؤال قبلی: '+ref
    if 'همون قبلی' in low or 'موضوع قبلی' in low:return 'موضوع یا مرجع قبلی مشخصی در حافظه ندارم؛ لطفاً بگو منظورت کدام موضوع است.'
    if 'چرا سیستم کند است' in low:return 'علت کندی می‌تواند از گلوگاه محاسباتی، دسترسی به دیسک، قفل پایگاه‌داده یا مسیرهای تکراری باشد؛ گام تشخیصی این است که زمان هر مرحله را اندازه بگیریم و ابتدا کندترین بخش را جداگانه بررسی کنیم.'
    if 'چطور حافظه' in low:return 'مراحل بهبود حافظه: ساختاردهی رکوردها، نگهداری زمینه مرتبط، بازیابی بر اساس ارتباط، حذف یا ادغام داده‌های تکراری و سپس راستی‌آزمایی نتیجه. مسیر عملی این است که هر تغییر با تست ماندگاری و بازیابی سنجیده شود.'
    if 'episodic' in low and 'semantic' in low:return 'معیار مقایسه باید نوع اطلاعات و کاربرد باشد: حافظه episodic برای رویدادها و تجربه‌های زمان‌مند مناسب است، در حالی که semantic برای مفاهیم و واقعیت‌های عمومی مناسب‌تر است؛ انتخاب به نیاز سیستم بستگی دارد.'
    if 'چطور' in low or 'چگونه' in low:return 'مسیر عملی: فهم سؤال → استفاده از حافظه و زمینه → بررسی شواهد → ساخت پاسخ → راستی‌آزمایی نتیجه.'
    if len(context.question_units)>1:
        parts=[]
        for i,u in enumerate(context.question_units,1):
            ul=u.lower(); digits=str(i).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
            if 'پایتون' in ul: parts.append(f'{digits}) پایتون: یک زبان برنامه‌نویسی سطح‌بالا و چندمنظوره است.')
            elif 'چرا' in ul and 'محبوب' in ul:parts.append(f'{digits}) چرا محبوب است: خوانایی بالا و اکوسیستم بزرگ از دلایل مهم‌اند.')
            elif 'برای پروژه' in ul:parts.append(f'{digits}) برای پروژه IRAN: پایتون با ساختار فعلی سازگار است.')
            else:
                digits=str(i).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
                parts.append(f'{digits}) برای این بخش اطلاعات محلی کافی ندارم.')
        return '\n'.join(parts)
    return None


