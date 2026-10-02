import re
from datetime import datetime
import re


class UserModel:
    """Persistent explicit user facts. Facts are separated from assumptions."""
    def __init__(self, memory, knowledge_graph, project_name="IRAN", gate=None):
        self.memory = memory; self.gate = gate
        self.knowledge = knowledge_graph
        self.project_name = project_name

    def _clean(self, text):
        return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))

    def _fact(self, predicate, obj, confidence):
        return {"subject":"user", "predicate":predicate, "object":str(obj).strip(),
                "confidence":confidence, "source":"explicit_user_statement", "type":"FACT"}

    def extract_explicit_facts(self, text):
        t = self._clean(text).rstrip(".!?؟")
        # A leading Persian/ASCII "no" commonly marks a correction. Strip it
        # before matching explicit facts so the corrected statement is durable.
        t = re.sub(r"^نه(?:[،,]\s*|\s+)", "", t, flags=re.I)
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
                if value and not creator_match and not re.fullmatch(role_words, value, re.I):
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
        # Explicit work/topic statements are durable user facts.
        m = re.match(r"^من\s+(?:روی|در)\s+(.+?)\s+کار\s+می[‌\s]?کنم$", t, re.I)
        if m:
            facts.append(self._fact("work_on", m.group(1).strip(" ،,"), .94))
        m = re.match(r"^(?:نه[،,]?\s*)?منظورم\s+(.+?)\s+(?:بود|است)$", t, re.I)
        if m:
            facts.append(self._fact("work_on", m.group(1).strip(" ،,"), .97))
        return facts

    def record(self, text):
        facts = self.extract_explicit_facts(text)
        # Explicit statements from the user are authoritative conversation facts.
        # They must be available immediately for the very next turn; the review
        # queue is reserved for inferred/autonomous learning, not user identity.
        stored = []
        gate_ctx = self.gate.bypass() if self.gate is not None else None
        if gate_ctx is not None:
            gate_ctx.__enter__()
        try:
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
        finally:
            if gate_ctx is not None:
                gate_ctx.__exit__(None, None, None)
        return stored

    def record_from_facts(self, facts):
        """Persist explicit structured user facts immediately.

        Inferred/autonomous knowledge still goes through LearningGate. Facts
        extracted directly from the user's own utterance follow the same
        authoritative bypass already used by record().
        """
        stored=[]
        gate_ctx = self.gate.bypass() if self.gate is not None else None
        if gate_ctx is not None:
            gate_ctx.__enter__()
        try:
            for fact in facts or []:
                meta=dict(fact); meta["timestamp"]=datetime.now().isoformat(timespec="microseconds")
                self.memory.add_semantic_fact(fact["subject"],fact["predicate"],fact["object"],fact["confidence"],fact["source"])
                if self.knowledge is not None:
                    try: self.knowledge.contradict(fact["subject"],fact["predicate"],fact["object"],fact["confidence"],fact["source"])
                    except Exception: pass
                self.memory.add("user_fact",str(meta),importance=.92,confidence=fact["confidence"],source=fact["source"])
                self.memory.add("semantic_fact_record",__import__("json").dumps(meta,ensure_ascii=False,sort_keys=True),
                                importance=.90,confidence=fact["confidence"],source=fact["source"])
                stored.append(meta)
        finally:
            if gate_ctx is not None:
                gate_ctx.__exit__(None, None, None)
        return stored

    def facts(self, predicate=None, limit=20):
        sql = "SELECT subject,predicate,value,confidence,source,updated_at FROM semantic_facts WHERE subject='user'"
        args = []
        if predicate:
            sql += " AND predicate=?"
            args.append(predicate)
        sql += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        args.append(int(limit))
        rows = self.memory.conn.execute(sql, tuple(args)).fetchall()
        return [{"subject":r[0],"predicate":r[1],"object":r[2],"confidence":r[3],"source":r[4],"timestamp":r[5],"type":"FACT"} for r in rows]

    def answer_identity(self, text):
        query = self._clean(text)
        if not re.search(r"(?:اسم|نام)(?:\s+من|م)\s+(?:چیست|چیه|چی(?:\s+بود)?|چه(?:\s+بود)?)", query):
            return None
        facts = self.current_belief('name', limit=1)
        if not facts:
            return 'UNKNOWN: هنوز نامی از شما در حافظه ثبت نشده است.'
        return f"اسم شما «{facts[0]['object']}» است."

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


# v0.34: structured names for user-owned entities (project/company/etc.).
# Raw history remains context; explicit named relations are stored as semantic facts.
_UserModel_extract_owned_base = UserModel.extract_explicit_facts

def _owned_entity_key(entity):
    value = re.sub(r"\s+", " ", str(entity or "").replace("\u200c", " ")).strip(" ،,:؛")
    value = re.sub(r"(?:\s+من)$", "", value).strip()
    return value

def _strip_persian_copula(value):
    value = str(value or "").strip(" ،,:؛")
    value = re.sub(r"\s+(?:است|هست|بود)$", "", value).strip()
    # Persian contracts vowel-final words: دانا + است -> داناست.
    if len(value) > 3 and value.endswith("ست") and value[-3] in "اوی":
        value = value[:-2].strip()
    return value

def _extract_explicit_facts_owned_names(self, text):
    raw = self._clean(text)
    # Memory directives are not part of the fact value.
    declarative = re.sub(
        r"(?:[،,]\s*)?(?:یادت\s+(?:بماند|بمونه)|یادت\s+باشه|به\s+خاطر\s+بسپار)\.?$",
        "", raw, flags=re.I,
    ).strip()
    facts = _UserModel_extract_owned_base(self, declarative)

    # Generic relation: "اسم <owned entity> من X است" / "اسم <entity>‌ام X است".
    # The entity label is data, not a hard-coded project/company list.
    pattern = re.compile(
        r"(?:اسم|نام)\s+"
        r"(?P<entity>[\wآ-ی‌-]+?)"
        r"(?:\s+من|‌?ام|م)\s+"
        r"(?P<value>.+?)"
        r"(?=[،,.!?؟]|(?:\s+حالا\b)|$)",
        re.I,
    )
    for match in pattern.finditer(declarative):
        entity = _owned_entity_key(match.group("entity"))
        value = _strip_persian_copula(match.group("value"))
        low_value = value.lower()
        if (not entity or not value or entity in {"من", "خودم"} or
                re.match(r"^(?:چی|چیه|چیست|چه|کدام|کدوم|چی\s+بود)", low_value)):
            continue
        fact = self._fact(f"owned_name:{entity}", value, .99)
        key = (fact["predicate"], fact["object"])
        if not any((x.get("predicate"), x.get("object")) == key for x in facts):
            facts.append(fact)
    return facts

UserModel.extract_explicit_facts = _extract_explicit_facts_owned_names


def _owned_name_entity_from_query(text):
    q = re.sub(r"\s+", " ", str(text or "").replace("\u200c", " ")).strip()
    # Explicit possessive query: اسم پروژه من چیه؟ / اسم شرکتم چی بود؟
    patterns = [
        r"(?:اسم|نام)\s+(?P<entity>[\wآ-ی-]+?)\s+من\s+(?:چی|چیه|چیست|چه|کدام|کدوم)",
        r"(?:اسم|نام)\s+(?P<entity>[\wآ-ی-]+?)(?:\s*ام|م)\s+(?:چی|چیه|چیست|چه|کدام|کدوم)",
    ]
    for pat in patterns:
        m = re.search(pat, q, re.I)
        if m:
            return _owned_entity_key(m.group("entity"))
    # Elliptical return: "برگردیم به پروژه قبلی؛ اسمش چی بود؟"
    if re.search(r"(?:اسمش|نامش)\s+(?:چی|چیه|چیست|چه)", q, re.I):
        m = re.search(r"(?P<entity>[\wآ-ی-]+)\s+قبلی", q, re.I)
        if m:
            return _owned_entity_key(m.group("entity"))
        return "*"
    return ""

def _answer_owned_name(self, text):
    entity = _owned_name_entity_from_query(text)
    if not entity:
        return None
    if entity == "*":
        rows = [x for x in self.facts(limit=100)
                if str(x.get("predicate", "")).startswith("owned_name:")]
        if not rows:
            return None
        fact = rows[0]
        entity = str(fact["predicate"]).split(":", 1)[1]
    else:
        rows = self.current_belief(f"owned_name:{entity}", limit=1)
        if not rows:
            return None
        fact = rows[0]
    return f"اسم {entity} شما «{fact['object']}» است."

UserModel.answer_owned_name = _answer_owned_name
UserModel.owned_name_entity_from_query = staticmethod(_owned_name_entity_from_query)
