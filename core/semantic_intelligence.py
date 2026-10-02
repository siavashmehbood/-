"""Semantic intelligence foundation for IRAN.

This module owns no decisions. It converts Persian utterances into an internal
linguistic/semantic contract, extracts explicit facts, resolves references and
ranks fact evidence. CognitiveSystem remains the only final decision owner.

External NLP frameworks are optional backends. The default fallback is local,
deterministic and offline so missing spaCy/Stanza/DeepPavlov/Haystack packages
can never make the runtime crash or silently revert to raw-history echo.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
import importlib.util
import json
import re
import time


def normalize_fa(text: str) -> str:
    value = str(text or "")
    value = value.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
    value = value.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    value = re.sub(r"[\u064b-\u065f\u0670\u06d6-\u06ed]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


@dataclass
class TokenAnalysis:
    text: str
    normalized: str
    lemma: str = ""
    pos: str = ""
    morphology: dict[str, str] = field(default_factory=dict)
    head: int = -1
    dependency: str = ""
    start: int = 0
    end: int = 0


@dataclass
class EntityMention:
    entity_id: str
    text: str
    entity_type: str
    role: str = ""
    start: int = -1
    end: int = -1
    confidence: float = 0.0
    provenance: str = "iran_fallback"


@dataclass
class LinguisticAnalysis:
    raw_text: str
    normalized_text: str
    language: str
    tokens: list[TokenAnalysis] = field(default_factory=list)
    sentences: list[str] = field(default_factory=list)
    entities: list[EntityMention] = field(default_factory=list)
    backend: str = "iran_fallback"
    capabilities: dict[str, bool] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class SemanticFact:
    subject: str
    relation: str
    value: str
    entity_type: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    source_turn: int = 0
    order: int = 0
    confidence: float = 0.0
    provenance: str = "explicit_user_statement"
    scope: str = "conversation"
    supersedes: str = ""

    def to_memory(self):
        return {
            "subject": self.subject,
            "predicate": self.relation,
            "object": self.value,
            "confidence": self.confidence,
            "source": self.provenance,
            "entity_type": self.entity_type,
            "attributes": dict(self.attributes),
            "source_turn": self.source_turn,
            "order": self.order,
            "scope": self.scope,
            "supersedes": self.supersedes,
            "type": "FACT",
        }


@dataclass
class SemanticQuery:
    subject: str = ""
    relation: str = ""
    entity_type: str = ""
    entity_id: str = ""
    value_hint: str = ""
    reference: str = ""
    confidence: float = 0.0


@dataclass
class EvidenceRecord:
    subject: str
    relation: str
    value: str
    entity_type: str = ""
    confidence: float = 0.0
    provenance: str = ""
    updated_at: str = ""
    score: float = 0.0
    superseded: bool = False
    reason: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class SemanticTurn:
    linguistic: LinguisticAnalysis
    utterance_type: str = "statement"
    facts: list[SemanticFact] = field(default_factory=list)
    query: SemanticQuery = field(default_factory=SemanticQuery)
    resolved_references: list[dict] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    semantic_answer: str = ""
    elapsed_ms: float = 0.0

    def public_trace(self):
        return {
            "backend": self.linguistic.backend,
            "utterance_type": self.utterance_type,
            "token_count": len(self.linguistic.tokens),
            "entity_count": len(self.linguistic.entities),
            "fact_count": len(self.facts),
            "query": asdict(self.query),
            "resolved_reference_count": len(self.resolved_references),
            "evidence_count": len(self.evidence),
            "elapsed_ms": self.elapsed_ms,
        }


class PersianLinguisticAnalyzer:
    """Stable internal linguistic representation with safe optional backends."""

    TYPE_WORDS = {
        "پروژه": "project", "محصول": "product", "شرکت": "organization",
        "سازمان": "organization", "تیم": "organization", "همکار": "person",
        "همکارم": "person", "دوست": "person", "دوستم": "person",
    }
    PRONOUNS = {"من", "تو", "او", "اون", "آن", "این", "همون", "همان", "ما", "شما"}
    QUESTION_WORDS = {"چی", "چیه", "چیست", "چه", "کدام", "کدوم", "کی", "چرا", "چطور", "چگونه", "کجا"}

    def __init__(self):
        self.optional = {
            "spacy": importlib.util.find_spec("spacy") is not None,
            "stanza": importlib.util.find_spec("stanza") is not None,
            "deeppavlov": importlib.util.find_spec("deeppavlov") is not None,
            "haystack": importlib.util.find_spec("haystack") is not None,
        }

    @staticmethod
    def _language(text):
        fa = sum("آ" <= c <= "ی" for c in text)
        en = sum("a" <= c.lower() <= "z" for c in text)
        return "mixed" if fa and en else "fa" if fa else "en" if en else "unknown"

    @staticmethod
    def _sentences(text):
        return [x.strip() for x in re.split(r"(?<=[.!؟?])\s+|[\n]+", text) if x.strip()] or ([text] if text else [])

    def analyze(self, text: str) -> LinguisticAnalysis:
        started = time.perf_counter()
        normalized = normalize_fa(text)
        tokens = []
        for idx, match in enumerate(re.finditer(r"[A-Za-z0-9_+-]+|[آ-ی]+", normalized)):
            raw = match.group(0)
            low = raw.lower()
            pos = "X"
            morph = {}
            if raw in self.PRONOUNS:
                pos = "PRON"
            elif raw in self.QUESTION_WORDS:
                pos = "PRON"; morph["PronType"] = "Int"
            elif re.fullmatch(r"\d+(?:\.\d+)?", raw):
                pos = "NUM"
            elif low in {"است", "هست", "بود", "شد", "شده", "دارم", "دارم", "کار", "میکنم", "می‌کنم"}:
                pos = "VERB"
            elif raw in self.TYPE_WORDS:
                pos = "NOUN"
            elif raw.endswith(("م", "ام")) and len(raw) > 3:
                pos = "NOUN"; morph["Poss"] = "Yes"; morph["Person"] = "1"
            tokens.append(TokenAnalysis(raw, low, low, pos, morph, -1, "", match.start(), match.end()))
        return LinguisticAnalysis(
            raw_text=str(text or ""), normalized_text=normalized,
            language=self._language(normalized), tokens=tokens,
            sentences=self._sentences(normalized), entities=[],
            backend="iran_fallback",
            capabilities={
                "tokens": True, "sentence_segmentation": True,
                "pos": True, "morphology": True,
                "lemma": True, "dependency": False, "ner": False,
                "spacy_available": self.optional["spacy"],
                "stanza_available": self.optional["stanza"],
            },
            elapsed_ms=round((time.perf_counter()-started)*1000, 3),
        )


class SemanticIntelligence:
    """Meaning/fact/reference layer subordinate to CognitiveSystem."""

    TYPE_ALIASES = {
        "پروژه": "project", "پروژه ای": "project", "پروژه‌ای": "project",
        "محصول": "product", "محصولمون": "product", "محصولمان": "product",
        "شرکت": "organization", "شرکتم": "organization", "شرکت من": "organization",
        "سازمان": "organization", "تیم": "organization",
        "همکار": "person", "همکارم": "person", "دوست": "person", "دوستم": "person",
    }
    TYPE_LABELS = {
        "project": "پروژه", "product": "محصول", "organization": "سازمان",
        "person": "شخص", "preference": "ترجیح",
    }
    QUESTION_MARKERS = ("؟", "?", "چی", "چیه", "چیست", "چه ", "کدام", "کدوم", "چطور", "چگونه")
    UNCERTAIN_MARKERS = ("شاید", "احتمالا", "احتمالاً", "فکر کنم", "گمان کنم")
    SPECULATION_MARKERS = ("اگر", "فرض کنیم", "ممکنه", "ممکن است")
    COMMAND_MARKERS = ("انجام بده", "بساز", "اجرا کن", "بررسی کن", "باز کن", "ببند")

    def __init__(self, memory):
        self.memory = memory
        self.linguistic = PersianLinguisticAnalyzer()

    @staticmethod
    def _slug(value):
        value = normalize_fa(value).lower()
        value = re.sub(r"[^0-9a-zآ-ی]+", "_", value).strip("_")
        return value[:80] or "entity"

    @classmethod
    def _entity_type_from_text(cls, text):
        n = normalize_fa(text)
        for alias, typ in sorted(cls.TYPE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in n:
                return typ
        return ""

    @staticmethod
    def _strip_copula(value):
        value = normalize_fa(value).strip(" ،,:؛.!؟?")
        value = re.sub(r"\s+(?:است|هست|بود|شد)$", "", value).strip()
        if len(value) > 3 and value.endswith("ست") and value[-3] in "اوی":
            value = value[:-2].strip()
        if len(value) > 2 and value.endswith("ه") and " " not in value:
            # Colloquial Xه is treated cautiously; preserve common lexical ه words.
            stem = value[:-1]
            if len(stem) >= 3:
                value = stem
        return value.strip(" «»\"'")

    @classmethod
    def _utterance_type(cls, text):
        n = normalize_fa(text)
        low = n.lower()
        if any(x in low for x in cls.COMMAND_MARKERS):
            return "command"
        if any(x in low for x in cls.UNCERTAIN_MARKERS):
            return "uncertain"
        if any(x in low for x in cls.SPECULATION_MARKERS):
            return "speculation"
        if low.startswith(("نه ", "نه،", "نه,")) or any(x in low for x in ("اسمش رو گذاشت", "اسمش شد", "اصلاح")):
            return "correction"
        if any(x in n for x in cls.QUESTION_MARKERS):
            return "question"
        if any(x in low for x in ("دوست دارم", "ترجیح میدم", "ترجیح می‌دم")):
            return "preference"
        return "statement"

    def _entity_id(self, typ, name, slots):
        if name:
            return f"{typ}:{self._slug(name)}"
        existing = (slots or {}).get(f"semantic.entity.{typ}")
        return str(existing or f"{typ}:current")

    def _latest_entity(self, slots, typ=""):
        slots = slots or {}
        if typ and slots.get(f"semantic.entity.{typ}"):
            return str(slots[f"semantic.entity.{typ}"])
        return str(slots.get("semantic.last_entity") or "")

    def _extract_named_entity(self, text, linguistic, slots, turn):
        n = normalize_fa(text)
        facts=[]; entities=[]
        # Generic "<entity> ... به اسم/نام X" frame. Vocabulary identifies
        # entity type, while the value itself is unrestricted.
        m = re.search(
            r"(?P<label>پروژه(?:\s*ای)?|محصول(?:مون|مان)?|شرکت(?:م|\s+من)?|سازمان|تیم)"
            r".{0,36}?(?:به\s+(?:اسم|نام)|اسمش|نامش)\s+"
            r"(?P<name>[A-Za-z0-9آ-ی][A-Za-z0-9آ-ی _-]{0,80}?)"
            r"(?=\s+(?:کار|برای|که|است|هست|بود|شد|دارم|داریم)|[،,.!?؟]|$)",
            n, re.I,
        )
        if m:
            typ=self._entity_type_from_text(m.group("label")) or "concept"
            name=self._strip_copula(m.group("name"))
            eid=self._entity_id(typ,name,slots)
            entities.append(EntityMention(eid,name,typ,"named_entity",m.start("name"),m.end("name"),.96,"iran_semantic_frame"))
            facts.append(SemanticFact(eid,"name",name,typ,source_turn=turn,confidence=.97,provenance="explicit_user_statement"))
            if typ=="project" and re.search(r"(?:روی|رو)\s+.*?کار\s+می",n):
                facts.append(SemanticFact("user","works_on",eid,"user",source_turn=turn,confidence=.95,provenance="explicit_user_statement"))
            purpose=re.search(r"(?:که\s+)?برای\s+(.+?)(?=[،,.!?؟]|$)",n)
            if purpose:
                value=normalize_fa(purpose.group(1)).strip(" ،,")
                if value:
                    facts.append(SemanticFact(eid,"purpose",value,typ,source_turn=turn,confidence=.90,provenance="explicit_user_statement"))
            return entities,facts

        # Generic possessive-name frame: "اسم محصولمون سپهره", "اسم شرکت من آریاست".
        m = re.search(
            r"(?:اسم|نام)\s+(?P<label>[آ-یA-Za-z]+?)(?:\s+من|مون|مان|م|ام)?\s+"
            r"(?P<name>[A-Za-z0-9آ-ی][A-Za-z0-9آ-ی _-]{1,80}?)"
            r"(?=[،,.!?؟]|\s+(?:است|هست|بود|شد)|$)",
            n, re.I,
        )
        if m and not re.search(r"^(?:چی|چیه|چیست|چه|کدوم|کدام)",m.group("name")):
            typ=self._entity_type_from_text(m.group("label"))
            if typ:
                name=self._strip_copula(m.group("name"))
                eid=self._entity_id(typ,name,slots)
                entities.append(EntityMention(eid,name,typ,"named_entity",m.start("name"),m.end("name"),.95,"iran_semantic_frame"))
                facts.append(SemanticFact(eid,"name",name,typ,source_turn=turn,confidence=.97,provenance="explicit_user_statement"))
        return entities,facts

    def _extract_person(self,text,slots,turn):
        n=normalize_fa(text)
        m=re.search(r"(?:یکی\s+از\s+)?(?P<role>همکار(?:ام|م)?|دوست(?:ام|م)?)\s+(?:اسمش|نامش)\s+(?P<name>[آ-یA-Za-z][آ-یA-Za-z _-]{1,60}?)(?=[،,.!?؟]|$)",n)
        if not m:return [],[]
        name=self._strip_copula(m.group("name")); role=normalize_fa(m.group("role"))
        eid=f"person:{self._slug(name)}"
        ent=EntityMention(eid,name,"person","colleague" if "همکار" in role else "friend",m.start("name"),m.end("name"),.96,"iran_semantic_frame")
        facts=[
            SemanticFact(eid,"name",name,"person",{"role":"colleague" if "همکار" in role else "friend"},turn,confidence=.97,provenance="explicit_user_statement"),
            SemanticFact("user","relation",eid,"user",{"role":"colleague" if "همکار" in role else "friend"},turn,confidence=.94,provenance="explicit_user_statement"),
        ]
        return [ent],facts

    def _extract_preference(self,text,turn):
        n=normalize_fa(text)
        m=re.search(r"(?:من\s+)?(?P<value>.+?)\s+(?:رو|را)?\s*(?:بیشتر\s+)?(?:دوست\s+دارم|ترجیح\s+می\s*دهم|ترجیح\s+میدم)$",n,re.I)
        if not m:return []
        value=normalize_fa(m.group("value")).strip(" ،,")
        if not value or any(q in value for q in ("چی","چه ","کدام","کدوم")):return []
        return [SemanticFact("user","preference",value,"preference",source_turn=turn,confidence=.94,provenance="explicit_user_statement")]

    def _extract_correction(self,text,slots,turn):
        n=normalize_fa(text)
        eid=self._latest_entity(slots)
        if not eid:return []
        m=re.search(r"(?:نه[،,]?\s*)?(?:اسمش|نامش)(?:\s+رو|\s+را)?\s*(?:گذاشتیم|کردیم|شد|هست|است)?\s*(?P<name>.+?)(?=[،,.!?؟]|$)",n,re.I)
        if not m:return []
        name=self._strip_copula(m.group("name"))
        if not name or name in {"چی","چیه","چیست","چه"}:return []
        typ=eid.split(":",1)[0] if ":" in eid else "concept"
        return [SemanticFact(eid,"name",name,typ,source_turn=turn,confidence=.98,provenance="explicit_user_correction",supersedes=f"{eid}|name")]

    def _query(self,text,slots):
        n=normalize_fa(text); low=n.lower()
        q=SemanticQuery()
        typ=self._entity_type_from_text(n)
        name_question=bool(re.search(r"(?:اسم|نام)(?:ش|\s+[^ ]+)?\s+(?:چی|چیه|چیست|چه|کدوم|کدام|چی\s+بود)",n,re.I))
        if name_question or re.search(r"(?:اسم|نام)\s+.*?\s+(?:چی|چه)\s+بود",n,re.I):
            q.relation="name"; q.entity_type=typ
        if any(x in low for x in ("پروژه ای که", "پروژه‌ای که", "پروژه قبلی", "اون پروژه", "همون پروژه")):
            q.entity_type="project"; q.relation=q.relation or "name"; q.reference="project_reference"
        if re.search(r"(?:همکار|دوست)(?:م|ام)?",n) and any(x in n for x in ("اسم","نام")):
            q.entity_type="person"; q.relation="name"; q.reference="person_relation"
        if ("قهوه" in n or "دوست" in n or "ترجیح" in n) and any(x in n for x in ("چطوری","چگونه","چه جوری","چی","یادم")):
            q.subject="user"; q.relation="preference"; q.value_hint="قهوه" if "قهوه" in n else ""
        if re.search(r"(?:منظورم|منظورت)\s+(?:اسم|نام)\s+",n):
            q.relation="name"; q.entity_type=typ
        if q.entity_type:
            q.entity_id=self._latest_entity(slots,q.entity_type)
        if not q.entity_id and any(x in n for x in ("اسمش","نامش","اون","همون","قبلی")):
            q.entity_id=self._latest_entity(slots)
            q.reference="latest_entity"
        if q.relation:
            q.confidence=.92 if q.entity_id or q.subject else .78
        return q

    def analyze(self,text,slots=None,source_turn=0):
        started=time.perf_counter(); slots=slots or {}
        linguistic=self.linguistic.analyze(text)
        utterance=self._utterance_type(text)
        entities=[]; facts=[]
        a,b=self._extract_named_entity(text,linguistic,slots,source_turn); entities+=a; facts+=b
        a,b=self._extract_person(text,slots,source_turn); entities+=a; facts+=b
        if utterance in {"preference","statement"}: facts+=self._extract_preference(text,source_turn)
        if utterance=="correction" or re.search(r"(?:اسمش|نامش).*(?:گذاشتیم|شد)",normalize_fa(text)):
            facts+=self._extract_correction(text,slots,source_turn)
        linguistic.entities.extend(entities)
        query=self._query(text,slots)
        resolved=[]
        if query.entity_id:
            resolved.append({"reference":query.reference or query.entity_type,"entity_id":query.entity_id,"confidence":query.confidence})
        return SemanticTurn(linguistic,utterance,facts,query,resolved,elapsed_ms=round((time.perf_counter()-started)*1000,3))

    def persist_explicit_facts(self,turn,user_model):
        if not turn.facts:return []
        # Explicit user statements are authoritative conversation facts. They
        # follow the same gate-bypass rule already used by UserModel.record.
        return user_model.record_from_facts([f.to_memory() for f in turn.facts])

    @staticmethod
    def _rows(memory):
        return memory.conn.execute(
            "SELECT subject,predicate,value,confidence,source,updated_at FROM semantic_facts ORDER BY updated_at DESC,id DESC"
        ).fetchall()

    def _rank_evidence(self,turn):
        q=turn.query
        if not q.relation:return []
        rows=self._rows(self.memory)
        newest={}; out=[]
        for s,p,v,c,src,updated in rows:
            key=(s,p)
            superseded=key in newest
            newest.setdefault(key,v)
            score=.0; reasons=[]
            if p==q.relation:score+=.45; reasons.append("relation")
            if q.entity_id and s==q.entity_id:score+=.38; reasons.append("entity_id")
            elif q.entity_type and str(s).startswith(q.entity_type+":"):score+=.22; reasons.append("entity_type")
            if q.subject and s==q.subject:score+=.30; reasons.append("subject")
            if q.value_hint and q.value_hint in normalize_fa(v):score+=.18; reasons.append("value_hint")
            score+=.10*float(c)
            if superseded:score-=.55
            if score>.25:
                out.append(EvidenceRecord(s,p,v,s.split(":",1)[0] if ":" in s else s,float(c),src,updated,round(score,3),superseded,"+".join(reasons)))
        out.sort(key=lambda x:(x.score,x.updated_at),reverse=True)
        return out

    def answer(self,turn):
        evidence=self._rank_evidence(turn); turn.evidence=evidence
        active=next((x for x in evidence if not x.superseded),None)
        if not active:return ""
        q=turn.query
        if q.relation=="name":
            label=self.TYPE_LABELS.get(q.entity_type or active.entity_type,"مورد")
            turn.semantic_answer=f"اسم {label} «{active.value}» است."
        elif q.relation=="preference":
            turn.semantic_answer=f"طبق ترجیحی که گفتی، «{active.value}» را دوست داری."
        return turn.semantic_answer

    def sync_foundation(self,turn,foundation):
        for ent in turn.linguistic.entities:
            foundation.set_slot("semantic.last_entity",ent.entity_id)
            foundation.set_slot("semantic.last_entity_type",ent.entity_type)
            foundation.set_slot(f"semantic.entity.{ent.entity_type}",ent.entity_id)
        if turn.facts:
            last=turn.facts[-1]
            foundation.set_slot("semantic.last_relation",last.relation)
            foundation.set_slot("semantic.last_subject",last.subject)
        if turn.query.relation:
            foundation.set_slot("semantic.requested_relation",turn.query.relation)
        foundation.save()

    @staticmethod
    def _tokens(text):
        return {x for x in re.findall(r"[A-Za-z0-9]+|[آ-ی]+",normalize_fa(text).lower()) if len(x)>1}

    def anti_echo(self,user_text,answer,recent_user_turns=None,semantic_answer=""):
        a=normalize_fa(answer); q=normalize_fa(user_text)
        if not a:return answer,False,""
        qt=self._tokens(q); at=self._tokens(a)
        sim=len(qt&at)/max(1,len(qt|at)) if qt and at else 0.0
        exact=a.strip(" «»'\".")==q.strip(" «»'\".")
        quoted_question=bool(re.search(r"(?:یادم هست گفتی|گفتی)\s*[:：]?\s*[«\"]",a)) and any(x in q for x in self.QUESTION_MARKERS)
        previous_echo=False
        for row in recent_user_turns or []:
            r=normalize_fa(row)
            if len(r)>8 and r in a and any(x in r for x in self.QUESTION_MARKERS):
                previous_echo=True;break
        if exact or sim>=.88 or quoted_question or previous_echo:
            if semantic_answer:
                return semantic_answer,True,"semantic_fact_repair"
            if any(x in q for x in self.QUESTION_MARKERS):
                return "UNKNOWN: پاسخ قابل اتکا از factهای معنایی موجود پیدا نکردم؛ متن خام گفتگو را به‌عنوان جواب برنمی‌گردانم.",True,"question_echo_blocked"
            return "متوجه شدم؛ این پیام به‌عنوان زمینه مکالمه ثبت شد و متن خودت را به‌عنوان پاسخ تکرار نمی‌کنم.",True,"statement_echo_blocked"
        return answer,False,""

    def backend_status(self):
        return {
            "active":"iran_fallback",
            "optional":dict(self.linguistic.optional),
            "offline":True,
            "decision_owner":"CognitiveSystem",
        }
