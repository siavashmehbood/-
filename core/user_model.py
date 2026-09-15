import re
from datetime import datetime


class UserModel:
    """Persistent explicit user facts. Facts are separated from assumptions."""
    def __init__(self, memory, knowledge_graph, project_name="IRAN"):
        self.memory = memory
        self.knowledge = knowledge_graph
        self.project_name = project_name

    def _clean(self, text):
        return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))

    def _fact(self, predicate, obj, confidence):
        return {"subject":"user", "predicate":predicate, "object":str(obj).strip(),
                "confidence":confidence, "source":"explicit_user_statement", "type":"FACT"}

    def extract_explicit_facts(self, text):
        t = self._clean(text).rstrip(".!?؟")
        facts = []
        man = "من"
        end = r"(?:هستم|ام)"
        creator = r"(?:سازنده|خالق|توسعه[-\s]?دهنده|برنامه[-\s]?نویس|مالک)"
        role_words = r"(?:دانشجو|وکیل|برنامه[-\s]?نویس|توسعه[-\s]?دهنده)"
        # Identity/role: support named identity, creator statements, and combined identity+role.
        m_name = re.match(r"^من\s+(.+?)\s*(?:،|,|[-–—])\s*(.+?)\s+(?:هستم|ام)$", t, re.I)
        if m_name:
            name = m_name.group(1).strip(" ،,.-–—")
            role_text = m_name.group(2).strip(" ،,.-–—")
            if name and not re.fullmatch(creator + r"(?:\s+.+)?", name, re.I):
                facts.append(self._fact("name", name, .98))
            if re.search(r"(?:سازنده|خالق|توسعه[-\s]?دهنده|برنامه[-\s]?نویس|مالک)", role_text, re.I):
                facts.append(self._fact("role", "creator", .97))
        else:
            m_name = re.match(r"^من\s+(.+?)\s+(?:هستم|ام)$", t, re.I)
            if m_name:
                value = m_name.group(1).strip(" ،,")
                creator_match = re.fullmatch(creator + r"(?:\s+.+)?", value, re.I)
                if value and not creator_match:
                    facts.append(self._fact("name", value, .98))
        if re.match(r"^" + man + r"\s+" + creator + r"(?:\s+.+?)?\s+" + end + r"$", t, re.I) or re.search(r"(?:^|\s)سازنده(?:\s|،|,)" , t):
            facts.append(self._fact("role", "creator", .97))
        m = re.match(r"^" + man + r"\s+(" + role_words + r")\s+" + end + r"$", t, re.I)
        if m:
            facts.append(self._fact("role", m.group(1), .95))
        m = re.match(r"^اسم\s+من\s+(.+?)\s+(?:است|هست)$", t, re.I)
        if m:
            facts.append(self._fact("name", m.group(1).strip(" ،,"), .98))
        likes = r"(?:دوست\s+دارم)"
        dislikes = r"(?:دوست\s+ندارم)"
        m = re.match(r"^" + man + r"\s+(.+?)\s+(" + likes + r"|" + dislikes + r")$", t, re.I)
        if m:
            pred = "likes" if re.fullmatch(likes, m.group(2), re.I) else "dislikes"
            value = re.sub(r"\s+را$", "", m.group(1).strip()).strip(" ،,")
            if value and value not in {"چی", "چه", "کدام", "کدوم", "چه چیزی", "چه‌چیزی"}:
                facts.append(self._fact(pred, value, .93))
        want = r"(?:می[‌\s]?خواهم|می[‌\s]?خواهم)"
        m = re.match(r"^" + man + r"\s+" + want + r"\s+(.+)$", t, re.I)
        if m:
            facts.append(self._fact("goal", m.group(1), .92))
        goal = r"هدفم"
        m = re.match(r"^" + goal + r"\s+(.+?)(?:\s+(?:است|هست))?$", t, re.I)
        if m:
            facts.append(self._fact("goal", m.group(1), .92))
        return facts

    def record(self, text):
        facts = self.extract_explicit_facts(text)
        stored = []
        for fact in facts:
            meta = dict(fact)
            meta["timestamp"] = datetime.now().isoformat(timespec="seconds")
            self.memory.add_semantic_fact(fact["subject"], fact["predicate"], fact["object"], fact["confidence"], fact["source"])
            if self.knowledge is not None:
                try:
                    self.knowledge.contradict(fact["subject"], fact["predicate"], fact["object"], fact["confidence"], fact["source"])
                except Exception:
                    pass
            self.memory.add("user_fact", str(meta), importance=.92, confidence=fact["confidence"], source=fact["source"])
            stored.append(meta)
        return stored

    def facts(self, predicate=None, limit=20):
        sql = "SELECT subject,predicate,value,confidence,source,updated_at FROM semantic_facts WHERE subject='user'"
        args = []
        if predicate:
            sql += " AND predicate=?"
            args.append(predicate)
        sql += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
        args.append(int(limit))
        rows = self.memory.conn.execute(sql, tuple(args)).fetchall()
        return [{"subject":r[0],"predicate":r[1],"object":r[2],"confidence":r[3],"source":r[4],"timestamp":r[5],"type":"FACT"} for r in rows]

    def current_belief(self, predicate, limit=1):
        """Return the current belief while retaining all historical fact rows."""
        rows = self.facts(predicate=predicate, limit=1000)
        ranked = sorted(rows, key=lambda row: (row.get('timestamp', ''),
                                               float(row.get('confidence', 0))), reverse=True)
        return ranked[:int(limit)]

    def contradictions(self, predicate=None):
        rows = self.facts(predicate=predicate, limit=1000)
        groups = {}
        for row in rows:
            groups.setdefault(row['predicate'], set()).add(row['object'])
        return {key: sorted(values) for key, values in groups.items() if len(values) > 1}

    def current_profile(self, limit=20):
        """Return one current belief per predicate without deleting historical facts."""
        rows = self.facts(limit=1000)
        latest = {}
        for row in rows:
            current = latest.get(row['predicate'])
            if current is None or (row.get('timestamp', ''), float(row.get('confidence', 0))) > (
                    current.get('timestamp', ''), float(current.get('confidence', 0))):
                latest[row['predicate']] = row
        return list(latest.values())[:int(limit)]

    def profile(self, query="", limit=12):
        facts = self.facts(limit=limit)
        if query:
            q = str(query).lower()
            matched = [f for f in facts if any(q in str(f[k]).lower() for k in ("predicate","object","source"))]
            facts = matched or facts
        return {"facts": facts[:limit], "count": len(facts[:limit]), "fact_only": True}


# v0.33: canonicalize explicit preference facts before persistence.
_UserModel_extract_base = UserModel.extract_explicit_facts
def _extract_explicit_facts_canonical(self, text):
    facts = _UserModel_extract_base(self, text)
    out=[]; seen=set()
    for fact in facts:
        f=dict(fact); obj=str(f.get('object','')).replace('\u200c',' ')
        obj=re.sub(r'\s+',' ',obj).strip(' ،,')
        if f.get('predicate') in ('likes','dislikes'):
            obj=re.sub(r'\s+را$','',obj).strip()
        f['object']=obj
        key=(f.get('predicate'),obj)
        if obj and key not in seen:
            seen.add(key); out.append(f)
    return out
UserModel.extract_explicit_facts = _extract_explicit_facts_canonical


# v0.33b: canonicalize and deduplicate persisted facts at read time as well.
_UserModel_facts_base = UserModel.facts
def _facts_canonical(self, predicate=None, limit=20):
    rows = _UserModel_facts_base(self, predicate=predicate, limit=max(int(limit)*3, 20))
    out=[]; seen=set()
    for f in rows:
        item=dict(f); obj=str(item.get('object','')).replace('\u200c',' ')
        obj=re.sub(r'\s+',' ',obj).strip(' ،,')
        if item.get('predicate') in ('likes','dislikes'):
            obj=re.sub(r'\s+را$','',obj).strip()
        item['object']=obj
        key=(item.get('predicate'),obj)
        if obj and key not in seen:
            seen.add(key); out.append(item)
        if len(out)>=int(limit): break
    return out
UserModel.facts = _facts_canonical
