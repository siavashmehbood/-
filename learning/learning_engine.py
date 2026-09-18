from dataclasses import dataclass, asdict
from pathlib import Path
import json, math, re
from datetime import datetime, timedelta
from collections import defaultdict, Counter

@dataclass
class Experience:
    goal:str; action:str; result:str; score:float; lesson:str; time:str
    intent:str='general'; strategy:str='default'; domain:str='general'
    objective:str=''; expected_effect:str=''; signal_source:str=''; evidence:str=''

class LearningEngine:
    """Continual local learning: experiences -> patterns -> rules -> strategy priors.
    Learning is automatic and local. It never calls an external model/service.
    """
    def __init__(self,path,gate=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.gate=gate
        self.rules_path=self.path.with_name('learned_rules.json')
        self.lessons_path=self.path.with_name('learned_lessons.json')
        self.experiences=[]; self.rules=[]; self.learned_lessons=[]; self._load(); self._load_rules(); self._load_lessons()

    def _load(self):
        if self.path.exists():
            try:
                rows=json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(rows,list): rows=[]
                seen=set(); kept=[]
                for row in reversed(rows[-10000:]):
                    key=self._stable_key(row)
                    if key in seen: continue
                    seen.add(key); kept.append(row)
                self.experiences=list(reversed(kept))[-10000:]
                if len(self.experiences)!=len(rows[-10000:]): self._save()
            except Exception: self.experiences=[]

    def _save(self):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.experiences,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.path)

    @staticmethod
    def _stable_key(row):
        def norm(v): return re.sub(r'\s+', ' ', str(v or '').strip().lower())
        return (norm(row.get('goal')), norm(row.get('action')), norm(row.get('result'))[:250],
                norm(row.get('intent','general')), norm(row.get('strategy','default')), norm(row.get('domain','general')))

    def _load_rules(self):
        if self.rules_path.exists():
            try: self.rules=json.loads(self.rules_path.read_text(encoding='utf-8'))[-2000:]
            except Exception: self.rules=[]

    def _load_lessons(self):
        if self.lessons_path.exists():
            try: self.learned_lessons=json.loads(self.lessons_path.read_text(encoding='utf-8'))[-5000:]
            except Exception: self.learned_lessons=[]

    def _save_lessons(self):
        tmp=self.lessons_path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.learned_lessons,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.lessons_path)

    def _save_rules(self):
        tmp=self.rules_path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.rules,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.rules_path)

    @staticmethod
    def _tokens(text):
        return set(re.findall(r'[\wآ-ی]+',str(text).lower()))

    def _similar(self,a,b):
        x=self._tokens(a); y=self._tokens(b)
        return len(x&y)/max(1,len(x|y))

    def _lesson_for(self,score):
        if score>=.82: return 'این راهبرد نتیجه خوبی داده است؛ نکته این است که بخش موفق آن حفظ شود و نتیجه دوباره بررسی شود.'
        if score>=.60: return 'بخش‌های مفید این راهبرد حفظ شده‌اند؛ برای دفعه بعد شواهد قوی‌تری جمع می‌شود.'
        return 'این راهبرد نتیجه کافی نداده است؛ باید علت خطا جدا شود و یک روش جایگزین آزمایش شود.'


    def record(self,goal,action,result,score,intent='general',strategy='default',domain='general',objective='',expected_effect='',signal_source='',evidence=''):
        score=max(0,min(1,float(score)))
        item=Experience(str(goal),str(action),str(result)[:4000],score,self._lesson_for(score),datetime.now().isoformat(timespec='seconds'),intent,strategy,domain,str(objective).strip(),str(expected_effect).strip(),str(signal_source).strip(),str(evidence).strip()[:1000])
        # Purpose gate: autonomous learning must have a concrete objective and verified success.
        # Routine observation is not learning; it only becomes learning when it produces a
        # reusable change/effect worth carrying into a future decision.
        if intent == 'autonomous':
            if not str(objective).strip() or not str(expected_effect).strip():
                return {"recorded": False, "learned": False, "reason": "no_learning_objective"}
            if score < 0.75:
                return {"recorded": False, "learned": False, "reason": "outcome_not_strong_enough"}
        if self.gate is not None and intent == 'autonomous':
            # Keep one autonomous learning item in the human-approval queue at a time.
            pending = [r for r in self.gate.pending(5000) if r.get('kind') == 'learning.record_experience'
                       and (r.get('payload') or {}).get('intent') == 'autonomous']
            if pending:
                return dict(pending[0])
            # Autonomous cycles must not create the same durable experience again.
            for row in self.gate.history(5000):
                payload = row.get('payload') or {}
                if (payload.get('goal') == item.goal and payload.get('action') == item.action
                    and payload.get('result') == item.result and payload.get('strategy') == item.strategy
                    and payload.get('domain') == item.domain and row.get('status') in {'pending', 'approved'}):
                    return dict(row)
        if self.gate is not None and not self.gate.bypassed:
            stable=self._stable_key(asdict(item))
            for row in self.gate.history(5000):
                if row.get('kind')!='learning.record_experience': continue
                payload=row.get('payload') or {}
                if self._stable_key(payload)==stable and row.get('status') in {'pending','approved'}:
                    return dict(row) if row.get('status')=='pending' else None
            proposal=self.gate.request('learning.record_experience',asdict(item), f'یادگیری جدید درباره «{goal}»')
            if proposal is not None: return proposal
        # Avoid storing exact duplicate traces repeatedly.
        duplicate=next((r for r in reversed(self.experiences[-80:]) if self._stable_key(r)==self._stable_key(asdict(item))),None)
        if duplicate:
            duplicate['score']=round((float(duplicate.get('score',0))+score)/2,4); duplicate['time']=item.time
        else: self.experiences.append(asdict(item))
        self.experiences=self.experiences[-10000:]; self._save()
        row=asdict(item)
        self.learn_from_experience(row)
        self._record_lesson(row)
        return row

    def _record_lesson(self,row):
        goal=str(row.get('goal','')).strip(); action=str(row.get('action','')).strip(); result=str(row.get('result','')).strip(); score=float(row.get('score',0))
        if not goal or not action: return None
        if score >= .75:
            text=f'برای «{goal}»، اجرای «{action}» با این نتیجه ثبت شد: «{result[:240]}». این الگو در موقعیت‌های مشابه باید دوباره آزمایش و در صورت تأیید استفاده شود.'
        elif score < .55:
            text=f'برای «{goal}»، اجرای «{action}» نتیجه کافی نداد: «{result[:240]}». این مسیر نباید بدون اصلاح دوباره تکرار شود.'
        else:
            text=f'برای «{goal}»، نتیجه اجرای «{action}» قطعی نیست: «{result[:240]}». قبل از تعمیم، شواهد بیشتری لازم است.'
        key=re.sub(r'\s+',' ',text).strip().lower()
        existing=next((x for x in self.learned_lessons if x.get('key')==key),None)
        if existing:
            existing['samples']=int(existing.get('samples',1))+1; existing['last_seen']=row.get('time','')
        else:
            self.learned_lessons.append({'lesson':text,'goal':goal,'action':action,'score':round(score,3),'samples':1,'first_seen':row.get('time',''),'last_seen':row.get('time',''),'key':key})
        self.learned_lessons=self.learned_lessons[-5000:]; self._save_lessons()
        return text

    def learned_lesson_rows(self,limit=20):
        return list(reversed(self.learned_lessons[-int(limit):]))

    def _rows_for(self,goal,intent=None,domain=None):
        rows=[]
        for r in self.experiences:
            if intent and r.get('intent')!=intent: continue
            if domain and r.get('domain')!=domain: continue
            sim=self._similar(goal,r.get('goal',''))
            if sim>.04 or str(goal).strip()==str(r.get('goal','')).strip(): rows.append((sim,r))
        return rows

    def lessons(self,goal,limit=8):
        rows=sorted(self._rows_for(goal),key=lambda x:x[0]*.75+float(x[1].get('score',0))*.25,reverse=True)
        return [r for _,r in rows[:int(limit)]]

    def success_rate(self,goal=None):
        rows=self.experiences if goal is None else self.lessons(goal,1000)
        return round(sum(float(x.get('score',0))>=.7 for x in rows)/len(rows),3) if rows else 0.

    def best_strategies(self,goal,limit=6):
        groups=defaultdict(list)
        for row in self.lessons(goal,1000): groups[row.get('strategy','default')].append(float(row.get('score',0)))
        ranked=sorted(((sum(v)/len(v),k,len(v)) for k,v in groups.items()),reverse=True)
        return [{'strategy':k,'score':round(s,3),'samples':n} for s,k,n in ranked[:int(limit)]]

    def _strategy_stats(self,rows):
        groups=defaultdict(list)
        for r in rows: groups[r.get('strategy','default')].append(float(r.get('score',0)))
        out=[]
        for k,v in groups.items():
            # recency-aware mean + confidence bonus for repeated evidence
            out.append((sum(v)/len(v)+min(.12,math.log1p(len(v))*.025),k,len(v)))
        return sorted(out,reverse=True)

    def recommended_strategy(self,goal,intent='general',domain='general'):
        rows=[r for _,r in self._rows_for(goal,intent,domain)]
        if rows:
            ranked=self._strategy_stats(rows)
            if ranked: return ranked[0][1]
        rows=[r for r in self.experiences if r.get('intent')==intent and r.get('domain')==domain]
        ranked=self._strategy_stats(rows)
        return ranked[0][1] if ranked else 'evidence-first'

    def failure_patterns(self,limit=10):
        bad=[x for x in self.experiences if float(x.get('score',0))<.55]
        return [x.get('lesson','')+': '+x.get('goal','') for x in bad[-int(limit):]]

    def adapt(self,goal,intent='general',domain='general'):
        similar=self.lessons(goal,8)
        return {
            'recommended_strategy':self.recommended_strategy(goal,intent,domain),
            'similar_experiences':similar[:5],
            'success_rate':self.success_rate(goal),
            'learned_rules':self.rules_for(goal,intent,domain,5),
            'strategy_evidence':self.best_strategies(goal,6),
        }

    def semantic_lessons(self,goal,intent=None,domain=None,limit=8):
        rows=[]
        for row in self.experiences:
            if intent and row.get('intent')!=intent: continue
            if domain and row.get('domain')!=domain: continue
            sim=self._similar(goal,row.get('goal',''))
            if sim>.04: rows.append((sim*.7+float(row.get('score',0))*.3,row))
        rows.sort(key=lambda x:x[0],reverse=True)
        return [r for _,r in rows[:int(limit)]]

    def failure_clusters(self,limit=8):
        groups=defaultdict(list)
        for row in self.experiences:
            if float(row.get('score',0))<.7:
                groups[(row.get('intent','general'),row.get('domain','general'),row.get('strategy','default'))].append(row)
        ranked=sorted(groups.items(),key=lambda x:len(x[1]),reverse=True)
        return [{'intent':k[0],'domain':k[1],'strategy':k[2],'count':len(v),'avg_score':round(sum(float(x.get('score',0)) for x in v)/len(v),3)} for k,v in ranked[:int(limit)]]

    def derive_rule(self,goal,intent='general',domain='general'):
        rows=self.semantic_lessons(goal,intent,domain,20)
        if not rows: return {'rule':'collect evidence before committing','confidence':.35,'samples':0}
        good=[r for r in rows if float(r.get('score',0))>=.75]; bad=[r for r in rows if float(r.get('score',0))<.55]
        if len(good)>=len(bad) and good: return {'rule':'reuse the successful strategy, then verify','confidence':round(min(.95,.45+len(good)*.06),3),'samples':len(rows)}
        return {'rule':'change strategy and increase evidence before action','confidence':round(min(.9,.45+len(bad)*.07),3),'samples':len(rows)}

    def learn_from_experience(self,row):
        """Automatically generalize repeated outcomes into durable rules."""
        goal=row.get('goal',''); intent=row.get('intent','general'); domain=row.get('domain','general'); strategy=row.get('strategy','default'); score=float(row.get('score',0))
        related=[r for r in self.experiences if r.get('intent')==intent and r.get('domain')==domain and self._similar(goal,r.get('goal',''))>=.18]
        if len(related)<2: return None
        strategy_rows=[r for r in related if r.get('strategy')==strategy]
        evidence_rows=strategy_rows if len(strategy_rows)>=2 else related
        mean=sum(float(r.get('score',0)) for r in evidence_rows)/len(evidence_rows)
        kind='success' if mean>=.75 else 'failure' if mean<.55 else 'mixed'
        if len(strategy_rows)>=2:
            rule_text=(f'برای هدف‌های مشابه، راهبرد «{strategy}» معمولاً موفق است.' if kind=='success' else f'برای هدف‌های مشابه، راهبرد «{strategy}» معمولاً نیاز به تغییر و شواهد بیشتر دارد.' if kind=='failure' else f'برای هدف‌های مشابه، نتیجهٔ راهبرد «{strategy}» متغیر است؛ قبل از اقدام شواهد بیشتری جمع کن.')
        else:
            best=max(related,key=lambda r: float(r.get('score',0)))
            best_strategy=str(best.get('strategy','default'))
            rule_text=f'برای هدف‌های مشابه، شواهد فعلی راهبرد «{best_strategy}» را نسبت به گزینه‌های دیگر ترجیح می‌دهد؛ نتیجه را مستقل بررسی کن.'
            strategy=strategy or best_strategy
        confidence=min(.95,.45+len(evidence_rows)*.04+abs(mean-.5)*.35)
        existing=next((r for r in self.rules if r.get('intent')==intent and r.get('domain')==domain and r.get('strategy')==strategy),None)
        payload={'rule':rule_text,'intent':intent,'domain':domain,'strategy':strategy,'samples':len(related),'mean_score':round(mean,3),'confidence':round(confidence,3),'updated_at':datetime.now().isoformat(timespec='seconds')}
        if existing: existing.update(payload)
        else: self.rules.append(payload)
        self.rules=self.rules[-2000:]; self._save_rules(); return payload

    def rules_for(self,goal,intent='general',domain='general',limit=5):
        rows=[]
        for r in self.rules:
            if intent and r.get('intent')!=intent: continue
            if domain and r.get('domain')!=domain: continue
            sim=self._similar(goal,r.get('rule',''))
            score=sim*.65+float(r.get('confidence',0))*.35
            if sim>.02 or r.get('strategy') in [x.get('strategy') for x in self.best_strategies(goal,6)]: rows.append((score,r))
        rows.sort(key=lambda x:x[0],reverse=True)
        return [r for _,r in rows[:int(limit)]]

    def update_from_feedback(self,goal,feedback,intent='general',domain='general'):
        """Convert explicit local feedback into a learning signal without an LLM."""
        t=str(feedback).strip().lower(); positive=any(x in t for x in ('خوبه','عالی','درسته','درست بود','ممنون','good','great','correct'))
        negative=any(x in t for x in ('بد بود','اشتباه','غلط','ضعیف','نه','wrong','bad'))
        if not (positive or negative): return {'learned':False,'reason':'feedback ambiguous'}
        score=.92 if positive and not negative else .18
        return self.record(goal,'explicit-feedback',str(feedback)[:1000],score,intent,'feedback',domain)

    def auto_maintenance(self, max_experiences=10000, max_rules=2000):
        """Periodic self-maintenance: dedupe, relearn rules, and remove stale weak rules."""
        seen={}; kept=[]
        for r in reversed(self.experiences[-int(max_experiences):]):
            key=(r.get('goal',''),r.get('action',''),r.get('result','')[:250])
            if key in seen: continue
            seen[key]=1; kept.append(r)
        self.experiences=list(reversed(kept))[-int(max_experiences):]
        # Rebuild rule evidence from current experience, keeping only rules with support.
        buckets=defaultdict(list)
        for r in self.experiences:
            if r.get('intent') and r.get('strategy'):
                buckets[(r.get('intent','general'),r.get('domain','general'),r.get('strategy','default'))].append(r)
        rebuilt=[]
        for (intent,domain,strategy),rows in buckets.items():
            if len(rows)<2: continue
            mean=sum(float(x.get('score',0)) for x in rows)/len(rows)
            if mean>=.78 or mean<.55:
                text=(f'برای کارهای مشابه در حوزه {domain}، راهبرد «{strategy}» شواهد {"موفق" if mean>=.78 else "ناموفق"} دارد؛ نتیجه را دوباره بررسی کن.')
                rebuilt.append({'rule':text,'intent':intent,'domain':domain,'strategy':strategy,'samples':len(rows),'mean_score':round(mean,3),'confidence':round(min(.95,.45+len(rows)*.035),3),'updated_at':datetime.now().isoformat(timespec='seconds')})
        # Preserve manually/previously learned rules that still have support.
        old={(r.get('intent'),r.get('domain'),r.get('strategy')):r for r in self.rules}
        for r in rebuilt:
            key=(r['intent'],r['domain'],r['strategy'])
            if key in old: old[key].update(r)
            else: old[key]=r
        self.rules=list(old.values())[-int(max_rules):]
        self._save(); self._save_rules()
        return {'experiences':len(self.experiences),'rules':len(self.rules),'rebuilt':len(rebuilt)}

    def stats(self):
        return {'experiences':len(self.experiences),'success_rate':self.success_rate(),'failure_patterns':len([x for x in self.experiences if float(x.get('score',0))<.55]),'strategies':len(set(x.get('strategy','default') for x in self.experiences)),'learned_rules':len(self.rules)}


# v0.27: explicit cross-task learning transfer benchmark primitive.
def _transfer(self, task_a, task_b, outcome_a=True, outcome_b_before=None):
    """Generalize a lesson from task A and retrieve/apply it to task B."""
    before = self.success_rate(task_b) if outcome_b_before is None else float(outcome_b_before)
    source = self.lessons(task_a, 8)
    if not source:
        return {'transferred': False, 'reason': 'no_source_experience', 'decision_changed': False}
    best = max(source, key=lambda r: float(r.get('score', 0)))
    rule = self.derive_rule(task_a, best.get('intent', 'general'), best.get('domain', 'general'))
    retrieved = self.rules_for(task_b, best.get('intent', 'general'), best.get('domain', 'general'), 5)
    applied = bool(retrieved) or rule.get('samples', 0) > 0
    decision = 'reuse successful strategy, then verify' if outcome_a and applied else 'collect evidence before committing'
    return {'transferred': applied, 'source_task': task_a, 'target_task': task_b,
            'rule': rule, 'retrieved_rules': retrieved, 'decision': decision,
            'decision_changed': applied, 'target_baseline': round(before, 3)}

LearningEngine.transfer = _transfer


# v0.29 Task C: outcome-backed transfer. Retrieval alone is never transfer success.
def _transfer_real(self, task_a, task_b, baseline_fn, transfer_fn, verify_fn, outcome_a=True):
    baseline=float(baseline_fn(task_b))
    source=self.lessons(task_a,8)
    if not source: return {'transfer_success':False,'reason':'no_source_experience','baseline_score':baseline}
    best=max(source,key=lambda r:float(r.get('score',0)))
    rule=self.derive_rule(task_a,best.get('intent','general'),best.get('domain','general'))
    retrieved=self.rules_for(task_b,best.get('intent','general'),best.get('domain','general'),5)
    if not retrieved and not rule.get('samples',0):
        return {'transfer_success':False,'reason':'no_retrievable_learning','baseline_score':baseline}
    applied=transfer_fn({'rule':rule,'experience':best,'retrieved_rules':retrieved})
    outcome=verify_fn(task_b,applied)
    score=float(outcome.get('score',0) if isinstance(outcome,dict) else outcome)
    verified=bool(outcome.get('verified',False)) if isinstance(outcome,dict) else False
    improvement=round(score-baseline,4)
    success=bool(outcome_a and applied and verified and improvement>0)
    return {'transfer_success':success,'baseline_score':round(baseline,4),'transfer_score':round(score,4),
            'improvement':improvement,'decision_before':outcome.get('decision_before') if isinstance(outcome,dict) else None,
            'decision_after':outcome.get('decision_after') if isinstance(outcome,dict) else None,
            'procedure_retrieved':bool(outcome.get('procedure_retrieved',False)) if isinstance(outcome,dict) else False,
            'skill_retrieved':bool(outcome.get('skill_retrieved',False)) if isinstance(outcome,dict) else False,
            'skill_applied':bool(applied),'outcome_verified':verified,'rule':rule,'retrieved_rules':retrieved}

LearningEngine.transfer_real=_transfer_real
