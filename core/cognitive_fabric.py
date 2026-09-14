from dataclasses import dataclass, field
from collections import Counter, defaultdict
import re
import math
from datetime import datetime

@dataclass
class SemanticIntent:
    name: str
    score: float
    evidence: list[str] = field(default_factory=list)

@dataclass
class EntityMention:
    text: str
    kind: str
    confidence: float
    role: str = 'object'

@dataclass
class DialogueFrame:
    topic: str = ''
    goal: str = ''
    intent: str = 'general'
    pending: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    references: dict = field(default_factory=dict)
    turn: int = 0

class AdvancedLanguage:
    """Offline Persian understanding layer: intent competition, entities, roles and references."""
    INTENTS = {
        'question': ('چرا','چطور','چگونه','آیا','چیست','کدام','چه کسی','؟','?'),
        'debug': ('خطا','ارور','باگ','خراب','کار نمی','نمی‌کند','مشکل','اشکال'),
        'build': ('بساز','ایجاد','پیاده','توسعه','طراحی','تولید','اضافه کن'),
        'inspect': ('بررسی','وضعیت','تحلیل','چک','گزارش','بازبینی','تشخیص'),
        'plan': ('برنامه','نقشه راه','مراحل','قدم','استراتژی','پلن','زمان‌بندی'),
        'command': ('اجرا','باز کن','ببند','بخوان','بنویس','حذف','ذخیره','انجام بده'),
        'memory': ('یادت','یادته','حافظه','قبلاً','قبلی','به خاطر','گفتیم'),
        'compare': ('مقایسه','فرق','تفاوت','بهتر','بدتر','کدام بهتر'),
        'status': ('وضعیت','سلامت','آنلاین','آماده','کار می‌کنی'),
    }
    def normalize(self, text):
        t=str(text).strip().replace('ي','ی').replace('ى','ی').replace('ك','ک')
        t=re.sub(r'[\u200c]{2,}','‌',t); t=re.sub(r'\s+',' ',t)
        return t

    def tokens(self, text):
        return re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*', self.normalize(text).lower())

    def intents(self, text):
        t=self.normalize(text).lower(); words=set(self.tokens(t)); ranked=[]
        for name,signals in self.INTENTS.items():
            hits=[s for s in signals if s in t or s in words]
            if hits:
                score=min(.99,.42 + .11*len(hits) + .03*sum(1 for s in hits if len(s)>3))
                ranked.append(SemanticIntent(name,round(score,3),hits))
        ranked.sort(key=lambda x:x.score, reverse=True)
        return ranked or [SemanticIntent('general',.45,[])]

    def goal(self, text):
        t=self.normalize(text)
        markers=('می‌خواهم','میخوام','می خواهم','میخواهم','هدفم','لازم دارم','باید','می‌خوام')
        for marker in markers:
            if marker in t:
                value=t.split(marker,1)[1].strip(' :،؛')
                if value:return value
        return t

    def entities(self, text):
        t=self.normalize(text); out=[]
        patterns=[('path',r'(?:[A-Za-z]:\\|/)[^\s]+'),('number',r'\b\d+(?:[.,]\d+)?\b'),
                  ('tech',r'(?i)\b(?:python|django|sqlite|windows|api|gui|json|github|vscode)\b')]
        spans=[]
        for kind,pattern in patterns:
            for m in re.finditer(pattern,t): spans.append((m.start(),m.end(),m.group(),kind))
        for token in re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_.:/\\-]{2,}',t):
            if len(token)>2 and token not in ('میخوام','می‌خواهم','برای','این','یک'): spans.append((t.find(token),t.find(token)+len(token),token,'concept'))
        seen=set()
        for _,_,value,kind in sorted(spans):
            key=(value.lower(),kind)
            if key not in seen: seen.add(key); out.append(EntityMention(value,kind,.86))
        return out[:40]

    def references(self, text, frame=None):
        t=self.normalize(text); refs={}
        previous=frame or {}
        pronouns=('این','اون','آن','همین','همون','قبلی','قبلیش','آن‌ها','اون‌ها')
        for p in pronouns:
            if p in t: refs[p]=previous.get('topic') or previous.get('goal','')
        return refs

    def parse(self, text, frame=None):
        t=self.normalize(text); intents=self.intents(t); entities=self.entities(t)
        goal=self.goal(t); top=intents[0]
        return {'text':t,'intent':top.name,'intent_score':top.score,'alternatives':[i.__dict__ for i in intents[1:4]],
                'goal':goal,'entities':[e.__dict__ for e in entities],'references':self.references(t,frame),
                'questions':re.split(r'[؟?]',t)[:-1],'tokens':self.tokens(t)}

class SemanticRetriever:
    """Lightweight local retrieval with recency, importance, lexical similarity and intent fit."""
    def _tokens(self,text): return set(re.sub(r'[^\wآ-ی ]',' ',str(text).lower()).split())
    def score(self, query, text, importance=.5, recency=1.0):
        a=self._tokens(query); b=self._tokens(text)
        if not a or not b:return 0.0
        overlap=len(a&b)/max(1,len(a)); phrase=1 if str(query).lower() in str(text).lower() else 0
        return round(.62*overlap+.18*phrase+.12*float(importance)+.08*float(recency),4)
    def rank(self, query, rows, limit=10):
        ranked=[]
        for row in rows:
            content=str(row[1] if isinstance(row,(list,tuple)) and len(row)>1 else row)
            importance=float(row[3]) if isinstance(row,(list,tuple)) and len(row)>3 else .5
            ranked.append((self.score(query,content,importance),row))
        return [r for _,r in sorted(ranked,key=lambda x:x[0],reverse=True)[:int(limit)]]

class CausalGraph:
    """Local causal memory: state -> action -> expected outcome with confidence."""
    def __init__(self): self.edges=[]
    def add(self,cause,action,effect,confidence=.5,source='local'):
        item={'cause':str(cause),'action':str(action),'effect':str(effect),'confidence':float(confidence),'source':source}
        for old in self.edges:
            if old['cause']==item['cause'] and old['action']==item['action'] and old['effect']==item['effect']:
                old['confidence']=max(old['confidence'],item['confidence']); return old
        self.edges.append(item); self.edges=self.edges[-2000:]; return item
    def predict(self,state,action):
        s=str(state).lower(); a=str(action).lower(); hits=[]
        for e in self.edges:
            cs=set(re.findall(r'[\wآ-ی]+',e['cause'].lower())); ss=set(re.findall(r'[\wآ-ی]+',s))
            if a in e['action'].lower() or len(cs&ss)>=max(1,min(2,len(cs))): hits.append(e)
        return sorted(hits,key=lambda x:x['confidence'],reverse=True)[:8]
    def counterfactual(self,state,action,alternative):
        p=self.predict(state,action); q=self.predict(state,alternative)
        return {'action':action,'alternative':alternative,'support':p[:3],'alternative_support':q[:3],
                'winner':action if sum(x['confidence'] for x in p)>=sum(x['confidence'] for x in q) else alternative}

class StrategyMemory:
    """Adaptive strategy selection using contextual success and failure penalties."""
    def __init__(self): self.stats=defaultdict(lambda:[0.0,0])
    def key(self,intent,domain='general',strategy='default'): return f'{intent}|{domain}|{strategy}'
    def update(self,intent,domain,strategy,score):
        k=self.key(intent,domain,strategy); self.stats[k][0]+=float(score); self.stats[k][1]+=1
    def rank(self,intent,domain,candidates):
        rows=[]
        for s in candidates:
            total,n=self.stats[self.key(intent,domain,s)]; empirical=total/n if n else .5
            prior=.55 if s in ('verify','smallest-safe','evidence-first') else .5
            rows.append((.7*empirical+.3*prior,s,n))
        return [{'strategy':s,'score':round(v,3),'samples':n} for v,s,n in sorted(rows,reverse=True)]

class ResponseComposer:
    """Builds transparent local answers from evidence instead of a single canned template."""
    def compose(self, parsed, memory=None, reasoning=None, decision=None, uncertainty=0.0):
        intent=parsed.get('intent','general'); goal=parsed.get('goal') or parsed.get('text','')
        parts=[]
        if intent=='question': parts.append(f'برداشت من از سؤال: «{goal}»')
        elif intent in ('build','plan'): parts.append(f'هدف ثبت شد: «{goal}»')
        elif intent=='debug': parts.append(f'مسئله را به‌عنوان عیب‌یابی «{goal}» در نظر گرفتم.')
        elif intent=='inspect': parts.append(f'موضوع بررسی: «{goal}».')
        else: parts.append(f'برداشت فعلی: «{goal}».')
        if parsed.get('alternatives'):
            alt=parsed['alternatives'][0]['name']; parts.append(f'تفسیر جایگزین را هم کنار نگه می‌دارم: «{alt}».')
        if memory: parts.append(f'{len(memory)} قطعه زمینه مرتبط در حافظه پیدا شد.')
        if reasoning:
            conclusion=reasoning.get('conclusion','')
            if conclusion: parts.append(f'نتیجه موقت: {conclusion}')
        if decision and decision.get('chosen'):
            parts.append(f'اقدام منتخب: «{decision["chosen"]}» با اطمینان {decision.get("confidence",0):.2f}.')
        if uncertainty>.35: parts.append('عدم‌قطعیت هنوز بالاست؛ قبل از تصمیم قطعی باید شواهد بیشتری جمع شود.')
        else: parts.append('نتیجه قطعی را فقط بعد از مشاهده و ارزیابی خروجی اعلام می‌کنم.')
        return ' '.join(parts)

# Preference rules: explicit comparison language outranks incidental references such as «قبلی».
_old_intents = AdvancedLanguage.intents
def _intent_priority(self, text):
    ranked = _old_intents(self, text)
    t = self.normalize(text).lower()
    if any(x in t for x in ('مقایسه','فرق','تفاوت','بهتره','بدتره','کدام بهتر','کدوم بهتر')):
        ranked = [x for x in ranked if x.name != 'compare'] + [SemanticIntent('compare', .93, ['explicit-comparison'])]
        ranked.sort(key=lambda x:x.score, reverse=True)
    return ranked
AdvancedLanguage.intents = _intent_priority


# Second-pass parser: preserve competing intents, constraints and explicit references.
_old_parse = AdvancedLanguage.parse

def _parse_v2(self,text,frame=None):
    base=_old_parse(self,text,frame)
    t=self.normalize(text)
    ranked=self.intents(t)
    base['intents']=[i.__dict__ for i in ranked[:5]]
    base['multi_intent']=len(ranked)>1
    base['constraints']=re.findall(r'(?:بدون|نباید|فقط|حداقل|حداکثر|ترجیحاً|مهمه که)\s+[^،؛.]+',t)
    base['negated']=bool(re.search(r'\b(?:نیست|نمی|نباید|بدون|نه)\b',t))
    base['ambiguity']=round(max(0.0,1.0-float(base.get('intent_score',.45))) + (.12 if len(ranked)>1 else 0),3)
    base['subgoals']=[x.strip() for x in re.split(r'\s+(?:و|بعد|سپس|ولی|اما)\s+',t) if len(x.strip())>3][:8]
    return base
AdvancedLanguage.parse = _parse_v2

# v0.22: richer Persian dialogue parsing: reference candidates, temporal phrases and question decomposition.
def _parse_v3(self,text,frame=None):
    base=_parse_v2(self,text,frame); t=self.normalize(text)
    refs={}; prev=frame or {}
    for marker in ('این','اون','آن','همین','همون','قبلی','قبلیش','همین یکی','اون یکی'):
        if marker in t:
            refs[marker]={'candidate':prev.get('topic') or prev.get('goal',''),'confidence':.68 if prev else .25}
    base['reference_candidates']=refs
    base['temporal_expressions']=[x for x in ('امروز','دیروز','فردا','پس‌فردا','هفته بعد','هفته قبل','ماه بعد','قبلاً','الان') if x in t]
    qs=[x.strip() for x in re.split(r'[؟?]',t) if x.strip()]
    base['question_units']=qs
    base['has_why']='چرا' in t; base['has_how']=any(x in t for x in ('چطور','چگونه','چه جوری','چجوری','چه‌طور'))
    base['has_compare']=any(x in t for x in ('کدام','کدوم','بهتر','مقایسه','فرق','تفاوت'))
    return base
AdvancedLanguage.parse=_parse_v3

# v0.28b: boundary-safe references and explicit action intents for Persian compound requests.
_base_intents_28b = AdvancedLanguage.intents
def _intents_28b(self, text):
    ranked = _base_intents_28b(self, text)
    t = self.normalize(text).lower()
    extra = []
    if re.search(r'(?:تست|آزمون|امتحان)\s*(?:بگیر|کن|بزن|اجرا)', t):
        extra.append(SemanticIntent('test', .90, ['test-action']))
    if re.search(r'(?:درستش کن|رفعش کن|اصلاحش کن|تعمیرش کن)', t):
        extra.append(SemanticIntent('repair', .90, ['repair-action']))
    merged = {x.name: x for x in ranked}
    for x in extra:
        merged[x.name] = x
    out = sorted(merged.values(), key=lambda x: x.score, reverse=True)
    return out
AdvancedLanguage.intents = _intents_28b

_base_parse_28b = AdvancedLanguage.parse
def _parse_28b(self, text, frame=None):
    base = _base_parse_28b(self, text, frame)
    t = self.normalize(text)
    refs = dict(base.get('reference_candidates', {}))
    for marker in ('همین یکی','اون یکی','همون','این','اون','آن','قبلی','قبلیش'):
        if re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])', t):
            prev = frame or {}
            refs[marker] = {'candidate': prev.get('topic') or prev.get('goal',''),
                            'confidence': .68 if prev else .25}
    base['reference_candidates'] = refs
    base['intents'] = [i.__dict__ for i in self.intents(t)[:8]]
    base['multi_intent'] = len(base['intents']) > 1
    return base
AdvancedLanguage.parse = _parse_28b

# v0.28c: remove legacy substring-only reference matches (e.g. «این» inside «اینترنت»).
_prev_parse_28c = AdvancedLanguage.parse
def _parse_28c(self, text, frame=None):
    base = _prev_parse_28c(self, text, frame)
    t = self.normalize(text)
    valid = {}
    for marker, value in base.get('reference_candidates', {}).items():
        if re.search(rf'(?<![آ-یA-Za-z0-9‌]){re.escape(marker)}(?![آ-یA-Za-z0-9‌])', t):
            valid[marker] = value
    base['reference_candidates'] = valid
    return base
AdvancedLanguage.parse = _parse_28c

# v0.28d: prioritize diagnostic intent when a why-question contains explicit failure evidence.
_prev_intents_28d = AdvancedLanguage.intents
def _intents_28d(self, text):
    ranked = _prev_intents_28d(self, text)
    t = self.normalize(text).lower()
    if 'چرا' in t and any(s in t for s in ('خطا','ارور','باگ','خراب','کار نمی','نمی‌کند','مشکل','اشکال')):
        ranked = [x for x in ranked if x.name != 'debug'] + [SemanticIntent('debug', .96, ['diagnostic-question'])]
        ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked
AdvancedLanguage.intents = _intents_28d

_prev_parse_28d = AdvancedLanguage.parse
def _parse_28d(self, text, frame=None):
    base = _prev_parse_28d(self, text, frame)
    t = self.normalize(text)
    if re.search(r'(?<![آ-یA-Za-z0-9‌])همونو(?![آ-یA-Za-z0-9‌])', t):
        prev = frame or {}
        base.setdefault('reference_candidates', {})['همونو'] = {
            'candidate': prev.get('topic') or prev.get('goal',''),
            'confidence': .68 if prev else .25,
        }
    return base
AdvancedLanguage.parse = _parse_28d

# v0.28e: preserve generic why-questions as question; diagnostic boost requires explicit fault evidence.
_prev_intents_28e = AdvancedLanguage.intents
def _intents_28e(self, text):
    ranked = _prev_intents_28e(self, text)
    t = self.normalize(text).lower()
    strong_fault = ('خطا','ارور','باگ','مشکل','اشکال','خرابی')
    if 'چرا' in t and not any(s in t for s in strong_fault):
        ranked = [x for x in ranked if x.name not in ('debug','question')]
        ranked.append(SemanticIntent('question', .93, ['why-question']))
        ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked
AdvancedLanguage.intents = _intents_28e

# v0.28f: distinguish failure-state questions from explanatory why-questions.
_prev_intents_28f = AdvancedLanguage.intents
def _intents_28f(self, text):
    ranked = _prev_intents_28f(self, text)
    t = self.normalize(text).lower()
    if 'چرا' in t and 'کار نمی' in t:
        ranked = [x for x in ranked if x.name not in ('question','debug')]
        ranked.append(SemanticIntent('debug', .96, ['failure-state']))
    elif 'چرا' in t and 'خطا دارد' in t and 'کار نمی' not in t:
        ranked = [x for x in ranked if x.name not in ('question','debug')]
        ranked.append(SemanticIntent('question', .94, ['explanatory-question']))
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked
AdvancedLanguage.intents = _intents_28f
