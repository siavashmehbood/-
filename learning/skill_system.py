import json
from pathlib import Path
from datetime import datetime
from .procedural_memory import ProceduralMemory


class SkillSystem:
    """Persistent skill registry over procedural memory; policy remains external."""
    def __init__(self, path, procedures=None):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.procedures = procedures or ProceduralMemory(self.path.with_name('procedures.json'))
        self.skills = []; self.compositions = []; self._load(); self._load_compositions()

    def _load(self):
        if self.path.exists():
            try: self.skills = json.loads(self.path.read_text(encoding='utf-8'))[-5000:]
            except Exception: self.skills = []

    def _save(self):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.skills,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.path)

    @property
    def compositions_path(self):
        return self.path.with_name('compositions.json')

    def _load_compositions(self):
        if self.compositions_path.exists():
            try: self.compositions=json.loads(self.compositions_path.read_text(encoding='utf-8'))[-2000:]
            except Exception: self.compositions=[]

    def _save_compositions(self):
        tmp=self.compositions_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.compositions,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(self.compositions_path)

    def upsert(self, name, description, domain, goal_patterns, procedure, preconditions=None,
               required_capabilities=None, risk='low', confidence=.6, skill_id=None):
        now=datetime.now().isoformat(timespec='seconds'); sid=skill_id or self._stable_id(name,domain)
        row=next((x for x in self.skills if x.get('skill_id')==sid),None)
        payload={'skill_id':sid,'name':str(name),'description':str(description),'domain':str(domain),
                 'goal_patterns':list(goal_patterns or []),'preconditions':list(preconditions or []),
                 'procedure':procedure,'required_capabilities':list(required_capabilities or []),
                 'risk':str(risk),'success_rate':0.,'confidence':round(float(confidence),4),
                 'usage_count':row.get('usage_count',0) if row else 0,'failure_count':row.get('failure_count',0) if row else 0,
                 'version':int(row.get('version',0))+1 if row else 1,'enabled':row.get('enabled',True) if row else True,
                 'created_at':row.get('created_at',now) if row else now,'updated_at':now}
        if row: row.update(payload)
        else: self.skills.append(payload)
        self._save(); return payload

    @staticmethod
    def _stable_id(name,domain):
        import hashlib
        return 'skill_'+hashlib.sha256((str(name)+'|'+str(domain)).encode()).hexdigest()[:16]

    def discover(self, goal, domain=None, limit=5):
        q=set(str(goal).lower().split()); ranked=[]
        for s in self.skills:
            if not s.get('enabled',True) or (domain and s.get('domain')!=domain): continue
            text=' '.join([s.get('name',''),s.get('description',''),' '.join(s.get('goal_patterns',[]))]).lower()
            overlap=len(q & set(text.split()))/max(1,len(q)); score=.65*overlap+.35*float(s.get('confidence',0))
            if overlap: ranked.append((score,s))
        ranked.sort(key=lambda x:x[0],reverse=True); return [x[1] for x in ranked[:int(limit)]]

    def retrieve(self, goal, domain=None, limit=5): return self.discover(goal,domain,limit)

    def retrieve_transfer(self, goal, domain=None, strategy=None, limit=5):
        """Find reusable skills for a new goal, including cross-goal transfer.

        Exact goal overlap is preferred, but a verified strategy can transfer
        to a novel goal when the learned skill is enabled and in the same
        domain (or explicitly marked as general).
        """
        direct = self.discover(goal, domain, limit)
        if direct: return direct
        candidates=[]
        for skill in self.skills:
            if not skill.get('enabled', True): continue
            if domain and skill.get('domain') not in (domain, 'general'): continue
            name=str(skill.get('name',''))
            if strategy and name == str(strategy):
                score=.70 + .20*float(skill.get('confidence',0)) + .10*min(1, int(skill.get('usage_count',0))/5)
                candidates.append((score,skill))
        candidates.sort(key=lambda item:item[0], reverse=True)
        return [skill for _,skill in candidates[:int(limit)]]

    def compose(self, goal, skills, context=None, limit=8):
        """Build a new deterministic multi-skill procedure after checking every skill."""
        candidates=[]; rejected=[]
        for skill in (skills or []):
            if not skill.get('enabled', True):
                rejected.append({'skill_id':skill.get('skill_id'),'reason':'disabled'}); continue
            check=self.check_preconditions(skill, context or {'evidence': True})
            if not check.get('applicable'):
                rejected.append({'skill_id':skill.get('skill_id'),'reason':'preconditions','missing':check.get('missing',[])})
                continue
            candidates.append(skill)
        steps=[]; skill_ids=[]; seen=set()
        for skill in candidates:
            proc=skill.get('procedure') or {}
            raw_steps=proc.get('steps',[]) if isinstance(proc,dict) else []
            for raw in raw_steps:
                if isinstance(raw,dict):
                    action=raw.get('action') or raw.get('tool')
                    expected=raw.get('expected_effect') or proc.get('expected_outcome','')
                else:
                    action=str(raw).strip(); expected=proc.get('expected_outcome','')
                if not action or action in seen: continue
                seen.add(action)
                steps.append({'order':len(steps)+1,'action':action,'expected_effect':str(expected),
                              'skill_id':skill.get('skill_id'),'skill_name':skill.get('name')})
                if skill.get('skill_id') not in skill_ids: skill_ids.append(skill.get('skill_id'))
                if len(steps)>=int(limit): break
            if len(steps)>=int(limit): break
        if len(skill_ids)<2 or len(steps)<2: return None
        import hashlib
        cid='composition_'+hashlib.sha256((str(goal)+'|'+'|'.join(x['action'] for x in steps)).encode()).hexdigest()[:16]
        conf=sum(float(s.get('confidence',0)) for s in candidates)/max(1,len(candidates))
        return {'composition_id':cid,'goal':str(goal),'skill_ids':skill_ids,'steps':steps,
                'confidence':round(conf,4),'rejected':rejected,'status':'candidate'}

    def promote_composition(self, composition, verified=True):
        """Persist a verified composition as a reusable higher-order procedure."""
        if not composition or not verified: return None
        now=datetime.now().isoformat(timespec='seconds')
        existing=next((x for x in self.compositions if x.get('composition_id')==composition.get('composition_id')),None)
        if existing:
            existing['verification_count']=int(existing.get('verification_count',0))+1
            existing['confidence']=round(min(.99,float(existing.get('confidence',.5))+.04),4)
            existing['updated_at']=now
        else:
            existing=dict(composition)
            existing.update({'verification_count':1,'failure_count':0,'enabled':True,'created_at':now,'updated_at':now})
            self.compositions.append(existing)
        self.compositions=self.compositions[-2000:]
        self._save_compositions()
        return existing

    def retrieve_compositions(self, goal, limit=5, verified_only=True):
        q=set(str(goal).lower().split()); ranked=[]
        for c in self.compositions:
            if not c.get('enabled',True): continue
            if verified_only and c.get('verification_count',0) < 1: continue
            text=str(c.get('goal','')).lower()+' '+' '.join(str(x.get('action','')) for x in c.get('steps',[]))
            overlap=len(q & set(text.split()))/max(1,len(q))
            score=.55*overlap+.30*float(c.get('confidence',0))+.15*min(1,int(c.get('verification_count',0))/5)
            if overlap: ranked.append((score,c))
        ranked.sort(key=lambda x:x[0],reverse=True)
        return [c for _,c in ranked[:int(limit)]]

    def retrieve_hierarchical(self, goal, domain=None, limit=5, max_level=None):
        """Retrieve enabled higher-order skills without bypassing normal policy checks."""
        ranked=[]; q=set(str(goal).lower().split())
        for skill in self.skills:
            if not skill.get('enabled', True) or not skill.get('is_composite'): continue
            if domain and skill.get('domain') not in (domain, 'general'): continue
            level=int(skill.get('composition_level', 0))
            if max_level is not None and level > int(max_level): continue
            text=' '.join([str(skill.get('name','')), str(skill.get('description','')),
                           ' '.join(map(str, skill.get('goal_patterns',[])))]) .lower()
            overlap=len(q & set(text.split()))/max(1,len(q))
            if overlap:
                score=.50*overlap+.35*float(skill.get('confidence',0))+.15*min(1,int(skill.get('usage_count',0))/5)
                ranked.append((score, skill))
        ranked.sort(key=lambda item:item[0], reverse=True)
        return [skill for _,skill in ranked[:int(limit)]]

    def expand_skill(self, skill_id, max_depth=8):
        """Expand a hierarchical skill into executable leaf actions, rejecting cycles."""
        root=next((x for x in self.skills if x.get('skill_id')==skill_id), None)
        if not root or not root.get('enabled', True): return []
        def walk(skill, depth, seen):
            if depth > int(max_depth): return []
            sid=skill.get('skill_id')
            if sid in seen: return []
            seen=seen | {sid}
            steps=(skill.get('procedure') or {}).get('steps', [])
            out=[]
            for raw in steps:
                action=raw.get('action') if isinstance(raw,dict) else str(raw)
                child_id=raw.get('skill_id') if isinstance(raw,dict) else None
                if child_id and child_id != sid:
                    child=next((x for x in self.skills if x.get('skill_id')==child_id),None)
                    if child and child.get('is_composite'):
                        out.extend(walk(child, depth+1, seen)); continue
                if action:
                    item=dict(raw) if isinstance(raw,dict) else {'action':action}
                    item.setdefault('origin_skill_id', sid)
                    out.append(item)
            return out
        return walk(root, 0, set())

    def check_preconditions(self, skill, context=None):
        return self.procedures.check_preconditions({'preconditions':skill.get('preconditions',[])},context)

    def apply(self, skill_id, context=None):
        row=next((x for x in self.skills if x.get('skill_id')==skill_id),None)
        if not row or not row.get('enabled',True): return {'applied':False,'reason':'skill_disabled_or_missing'}
        check=self.check_preconditions(row,context); 
        if not check['applicable']: return {'applied':False,'reason':'skill_not_applicable','missing':check['missing']}
        row['usage_count']=int(row.get('usage_count',0))+1; row['updated_at']=datetime.now().isoformat(timespec='seconds'); self._save()
        return {'applied':True,'skill_id':skill_id,'procedure':row.get('procedure')}

    def update_outcome(self, skill_id, success):
        row=next((x for x in self.skills if x.get('skill_id')==skill_id),None)
        if not row:return None
        if not success: row['failure_count']=int(row.get('failure_count',0))+1
        total=int(row.get('usage_count',0)); old=float(row.get('success_rate',0)); sample=1.0 if success else 0.0
        row['success_rate']=round(old*.8+sample*.2,4); row['confidence']=round(max(.05,min(.99,float(row.get('confidence',.5)) + (.03 if success else -.08))),4)
        if not success and row['failure_count']>=3 and row['success_rate']<.35: row['enabled']=False
        row['updated_at']=datetime.now().isoformat(timespec='seconds'); self._save(); return row

    def record_execution(self, skill_id, success, verified=True, reason=''):
        """Record a verified execution and update trust without bypassing policy."""
        row=next((x for x in self.skills if x.get('skill_id')==skill_id),None)
        if not row: return None
        row['execution_count']=int(row.get('execution_count',0))+1
        row['usage_count']=int(row.get('usage_count',0))+1
        if verified:
            row['verified_execution_count']=int(row.get('verified_execution_count',0))+1
        if success:
            row['successful_execution_count']=int(row.get('successful_execution_count',0))+1
        else:
            row['failed_execution_count']=int(row.get('failed_execution_count',0))+1
        self.update_outcome(skill_id, bool(success))
        row=next((x for x in self.skills if x.get('skill_id')==skill_id),row)
        row['last_execution_success']=bool(success)
        if reason: row['last_execution_reason']=str(reason)
        row['updated_at']=datetime.now().isoformat(timespec='seconds')
        self._save()
        return row

    def execution_policy(self, skill, min_confidence=.35, max_failures=3):
        """Return whether a skill is trusted enough for autonomous reuse."""
        if not skill or not skill.get('enabled',True): return {'allowed':False,'reason':'disabled'}
        confidence=float(skill.get('confidence',0))
        failures=int(skill.get('failure_count',0))
        if confidence < float(min_confidence): return {'allowed':False,'reason':'low_confidence'}
        if failures >= int(max_failures) and float(skill.get('success_rate',0)) < .5:
            return {'allowed':False,'reason':'repeated_failures'}
        return {'allowed':True,'reason':'trusted'}
    def disable(self, skill_id, reason='manual'): return self._set_enabled(skill_id,False,reason)
    def enable(self, skill_id): return self._set_enabled(skill_id,True,'re-enabled')
    def _set_enabled(self, skill_id, enabled, reason):
        row=next((x for x in self.skills if x.get('skill_id')==skill_id),None)
        if not row:return None
        row['enabled']=bool(enabled); row['updated_at']=datetime.now().isoformat(timespec='seconds'); row['status_reason']=reason; self._save(); return row

# v0.45: verified compositions can become higher-order skills.
def _promote_composition_as_skill(self, composition, domain="task", max_level=8):
    if not composition or composition.get("status") not in ("candidate", "verified"):
        return None
    steps = list(composition.get("steps") or [])
    source_ids = list(composition.get("skill_ids") or [])
    if len(steps) < 2 or len(source_ids) < 2:
        return None
    source_levels=[]
    for sid in source_ids:
        source=next((x for x in self.skills if x.get("skill_id")==sid), None)
        if source:
            source_levels.append(int(source.get("composition_level", 0)))
    level = (max(source_levels) + 1) if source_levels else 1
    if level > int(max_level):
        return None
    name = "composed:" + str(composition.get("composition_id"))
    procedure = {
        "steps": [dict(x) for x in steps],
        "expected_outcome": str(composition.get("goal", "")),
        "kind": "hierarchical-composition",
        "composition_id": composition.get("composition_id"),
        "source_skill_ids": source_ids,
        "composition_level": level,
    }
    skill = self.upsert(
        name=name,
        description="Verified higher-order skill derived from composition " + str(composition.get("composition_id")),
        domain=domain,
        goal_patterns=[str(composition.get("goal", ""))],
        procedure=procedure,
        preconditions=[],
        required_capabilities=[],
        risk="low",
        confidence=float(composition.get("confidence", .5)),
        skill_id="skill_composition_" + str(composition.get("composition_id", "")).replace("composition_", ""),
    )
    skill["is_composite"] = True
    skill["composition_level"] = level
    skill["source_composition_id"] = composition.get("composition_id")
    skill["source_skill_ids"] = source_ids
    skill["source_composition_ids"] = [composition.get("composition_id")]
    skill["max_expansion_depth"] = int(max_level)
    skill["updated_at"] = datetime.now().isoformat(timespec="seconds")
    self._save()
    return skill

SkillSystem.promote_composition_as_skill = _promote_composition_as_skill
