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
import os
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
        self.backend_preference=os.environ.get("IRAN_NLP_BACKEND","fallback").strip().lower()
        self._stanza_pipeline=None
        self._spacy_nlp=None
        self.last_backend_error=""
        self.last_backend="iran_fallback"

    @staticmethod
    def _language(text):
        fa = sum("آ" <= c <= "ی" for c in text)
        en = sum("a" <= c.lower() <= "z" for c in text)
        return "mixed" if fa and en else "fa" if fa else "en" if en else "unknown"

    @staticmethod
    def _sentences(text):
        return [x.strip() for x in re.split(r"(?<=[.!؟?])\s+|[\n]+", text) if x.strip()] or ([text] if text else [])

    def _analyze_stanza(self,text):
        if not self.optional["stanza"]:
            return None
        try:
            import stanza
            if self._stanza_pipeline is None:
                # Never download at runtime. The backend is opt-in and only works
                # when Persian resources have already been installed locally.
                self._stanza_pipeline=stanza.Pipeline(
                    lang="fa",processors="tokenize,mwt,pos,lemma,depparse,ner",
                    download_method=None,verbose=False,use_gpu=False)
            started=time.perf_counter(); doc=self._stanza_pipeline(str(text or ""))
            tokens=[]; offset=0
            for sentence in doc.sentences:
                for word in sentence.words:
                    raw=str(word.text); pos=str(getattr(word,"upos","") or "")
                    feats={}
                    raw_feats=str(getattr(word,"feats","") or "")
                    for item in raw_feats.split("|"):
                        if "=" in item:
                            k,v=item.split("=",1); feats[k]=v
                    start=normalize_fa(text).find(normalize_fa(raw),offset)
                    start=max(0,start); end=start+len(raw); offset=end
                    tokens.append(TokenAnalysis(
                        raw,normalize_fa(raw).lower(),str(getattr(word,"lemma","") or raw),
                        pos,feats,int(getattr(word,"head",0) or 0)-1,
                        str(getattr(word,"deprel","") or ""),start,end))
            entities=[]
            for ent in getattr(doc,"ents",[]) or []:
                entities.append(EntityMention(
                    f"{str(ent.type).lower()}:{SemanticIntelligence._slug(ent.text)}",
                    str(ent.text),str(ent.type).lower(),"ner",
                    int(getattr(ent,"start_char",-1) or -1),int(getattr(ent,"end_char",-1) or -1),
                    .85,"stanza:fa"))
            self.last_backend="stanza:fa"
            return LinguisticAnalysis(
                raw_text=str(text or ""),normalized_text=normalize_fa(text),
                language=self._language(normalize_fa(text)),tokens=tokens,
                sentences=[str(s.text) for s in doc.sentences],entities=entities,
                backend="stanza:fa",
                capabilities={"tokens":True,"sentence_segmentation":True,"pos":True,
                              "morphology":True,"lemma":True,"dependency":True,"ner":True,
                              "spacy_available":self.optional["spacy"],
                              "stanza_available":True},
                elapsed_ms=round((time.perf_counter()-started)*1000,3))
        except Exception as exc:
            self.last_backend_error=f"stanza:{type(exc).__name__}"
            return None

    def _analyze_spacy(self,text):
        if not self.optional["spacy"]:
            return None
        try:
            import spacy
            if self._spacy_nlp is None:
                self._spacy_nlp=spacy.blank("fa")
                if "sentencizer" not in self._spacy_nlp.pipe_names:
                    self._spacy_nlp.add_pipe("sentencizer")
            started=time.perf_counter(); doc=self._spacy_nlp(str(text or ""))
            tokens=[TokenAnalysis(
                t.text,normalize_fa(t.text).lower(),str(t.lemma_ or t.text),
                str(t.pos_ or ""),{},int(t.head.i) if t.head is not None else -1,
                str(t.dep_ or ""),int(t.idx),int(t.idx+len(t.text))) for t in doc]
            self.last_backend="spacy:fa-blank"
            return LinguisticAnalysis(
                raw_text=str(text or ""),normalized_text=normalize_fa(text),
                language=self._language(normalize_fa(text)),tokens=tokens,
                sentences=[str(s.text) for s in doc.sents],entities=[],
                backend="spacy:fa-blank",
                capabilities={"tokens":True,"sentence_segmentation":True,"pos":False,
                              "morphology":False,"lemma":False,"dependency":False,"ner":False,
                              "spacy_available":True,"stanza_available":self.optional["stanza"]},
                elapsed_ms=round((time.perf_counter()-started)*1000,3))
        except Exception as exc:
            self.last_backend_error=f"spacy:{type(exc).__name__}"
            return None

    def analyze(self, text: str) -> LinguisticAnalysis:
        # Heavy NLP is lazy/opt-in: no model downloads, no startup penalty.
        if self.backend_preference=="stanza":
            result=self._analyze_stanza(text)
            if result is not None:return result
        elif self.backend_preference=="spacy":
            result=self._analyze_spacy(text)
            if result is not None:return result
        self.last_backend="iran_fallback"
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


class SemanticEvidenceRetriever:
    """Haystack-style retrieval contract over IRAN's existing semantic store.

    Storage remains Memory; this class only filters/ranks evidence with metadata
    and provenance. No vector database, cloud service or parallel memory exists.
    """
    def __init__(self,memory):
        self.memory=memory

    def rows(self):
        return self.memory.conn.execute(
            "SELECT subject,predicate,value,confidence,source,created_at,updated_at "
            "FROM semantic_facts ORDER BY updated_at DESC,id DESC"
        ).fetchall()

    def related_entity(self,relation):
        rows=self.memory.conn.execute(
            "SELECT value FROM semantic_facts WHERE subject='user' AND predicate=? "
            "ORDER BY updated_at DESC,id DESC LIMIT 1",(str(relation),)
        ).fetchone()
        return str(rows[0]) if rows else ""

    def entity_by_ordinal(self,entity_type,index):
        rows=self.memory.conn.execute(
            "SELECT subject,MIN(created_at) first_seen FROM semantic_facts "
            "WHERE subject LIKE ? GROUP BY subject ORDER BY first_seen ASC",
            (str(entity_type)+":%",)
        ).fetchall()
        try:return str(rows[int(index)-1][0])
        except (IndexError,ValueError,TypeError):return ""

    def rank(self,query):
        if not query.relation:return []
        rows=self.rows(); newest={}; out=[]
        for s,p,v,c,src,created,updated in rows:
            key=(s,p); superseded=key in newest; newest.setdefault(key,v)
            score=.0; reasons=[]
            if p==query.relation:score+=.45; reasons.append("relation")
            if query.entity_id and s==query.entity_id:score+=.38; reasons.append("entity_id")
            elif query.entity_type and str(s).startswith(query.entity_type+":"):score+=.22; reasons.append("entity_type")
            if query.subject and s==query.subject:score+=.30; reasons.append("subject")
            if query.value_hint and query.value_hint in normalize_fa(v):score+=.18; reasons.append("value_hint")
            score+=.10*float(c)
            if superseded:score-=.55
            if score>.25:
                out.append(EvidenceRecord(
                    s,p,v,s.split(":",1)[0] if ":" in s else s,float(c),src,updated,
                    round(score,3),superseded,"+".join(reasons)))
        out.sort(key=lambda x:(x.score,x.updated_at),reverse=True)
        return out


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
        self.retriever = SemanticEvidenceRetriever(memory)

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

    def _token_frame(self, linguistic, slots, turn):
        """Extract generic relation frames from token structure, not test phrases.

        This is the deterministic fallback equivalent of matcher/dependency
        concepts from spaCy/Stanza: downstream code consumes the same internal
        token/entity/fact contract regardless of backend.
        """
        toks=[t.normalized for t in linguistic.tokens]
        if not toks:
            return [],[]
        entities=[]; facts=[]
        # Find a known entity-type noun, then an open-class name after an
        # explicit naming relation (اسم/نام). The name token is unrestricted.
        for i,tok in enumerate(toks):
            typ=self._entity_type_from_text(tok)
            if not typ:
                continue
            name_idx=-1
            for j in range(i+1,min(len(toks),i+8)):
                if toks[j] in {"اسم","نام"}:
                    name_idx=j+1
                    break
            if name_idx<0 or name_idx>=len(toks):
                continue
            while name_idx<len(toks) and toks[name_idx] in {"ش","من","به","رو","را"}:
                name_idx+=1
            if name_idx>=len(toks):
                continue
            candidate=toks[name_idx]
            if candidate in self.QUESTION_MARKERS or candidate in {"چی","چیه","چیست","چه","کدام","کدوم"}:
                continue
            candidate=self._strip_copula(candidate)
            if not candidate:
                continue
            eid=self._entity_id(typ,candidate,slots)
            entities.append(EntityMention(eid,candidate,typ,"token_relation",-1,-1,.82,"iran_token_frame"))
            facts.append(SemanticFact(eid,"name",candidate,typ,source_turn=turn,
                                      confidence=.84,provenance="explicit_user_statement:token_frame"))
            if typ=="project" and any(x in toks for x in ("کار","دارم")):
                facts.append(SemanticFact("user","works_on",eid,"user",source_turn=turn,
                                          confidence=.82,provenance="explicit_user_statement:token_frame"))
            break
        return entities,facts

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
            r"(?:اسم|نام)\s+(?P<label>[آ-یA-Za-z]+?)(?:\s+من|\s*(?:مون|مان|ام|م))?\s+"
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
        relation="colleague" if "همکار" in role else "friend"
        facts=[
            SemanticFact(eid,"name",name,"person",{"role":relation},turn,confidence=.97,provenance="explicit_user_statement"),
            SemanticFact("user",relation,eid,"user",{"role":relation},turn,confidence=.94,provenance="explicit_user_statement"),
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
        # Entity linking: mention of a previously stored entity name binds the
        # query to that semantic entity instead of relying only on recency.
        try:
            for subject,predicate,value,confidence,source,created,updated in self.retriever.rows():
                if predicate=="name" and normalize_fa(value) and normalize_fa(value) in n:
                    q.entity_id=str(subject)
                    if ":" in q.entity_id:
                        q.entity_type=q.entity_id.split(":",1)[0]
                    q.reference="entity_link"
                    break
        except Exception:
            pass
        short_name_reference=bool(re.fullmatch(r"\s*(?:اسمش|نامش)\s*[؟?]?\s*",n,re.I))
        name_question=bool(re.search(r"(?:اسم|نام)(?:ش|\s+[^ ]+)?\s+(?:چی|چیه|چیست|چه|کدوم|کدام|چی\s+بود)",n,re.I))
        if short_name_reference or name_question or re.search(r"(?:اسم|نام)\s+.*?\s+(?:چی|چه)\s+بود",n,re.I):
            q.relation="name"; q.entity_type=typ
        if any(x in low for x in ("پروژه ای که", "پروژه‌ای که", "پروژه قبلی", "اون پروژه", "همون پروژه")):
            q.entity_type="project"; q.relation=q.relation or "name"; q.reference="project_reference"
        if q.entity_type=="project" and any(x in low for x in ("روش کار", "روی آن کار", "روی اون کار", "روی همون کار")):
            q.entity_id=self.retriever.related_entity("works_on")
            q.reference="works_on"
        # "اسم پروژه من ..." can also be stored as a durable raw user
        # memory from older versions. Promote that explicit binding into the
        # semantic evidence store only when the user explicitly asks for it.
        if q.entity_type=="project" and q.relation=="name" and re.search(r"(?:اسم|نام)\\s+پروژه\\s+من", n, re.I):
            try:
                for kind, content, created in self.memory.search(n, 20):
                    m=re.search(r"(?:اسم|نام)\\s+پروژه(?:\\s+من)?\\s+([آ-یA-Za-z0-9_-]+)\\s+(?:هست|است|بود)", normalize_fa(content), re.I)
                    if m:
                        value=self._strip_copula(m.group(1))
                        if value:
                            eid=f"project:{self._slug(value)}"
                            q.entity_id=eid
                            q.reference="explicit_durable_project_name"
                            now=datetime.now().isoformat(timespec="microseconds")
                            self.memory.conn.execute(
                                "INSERT OR IGNORE INTO semantic_facts(subject,predicate,value,confidence,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                                (eid,"name",value,.97,"durable_explicit_memory",now,now))
                            self.memory.conn.execute(
                                "INSERT OR IGNORE INTO semantic_facts(subject,predicate,value,confidence,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                                ("user","works_on",eid,.90,"durable_explicit_memory",now,now))
                            self.memory.conn.commit()
                            break
            except Exception:
                pass
        if q.entity_type=="project" and q.relation=="name" and re.search(r"(?:اسم|نام)\\s+پروژه\\s+من", n, re.I):
            owned=self.retriever.related_entity("works_on")
            if owned:
                q.entity_id=owned
                q.reference="works_on"
        ordinal={"اول":1,"دوم":2,"سوم":3}
        if q.entity_type:
            for marker,index in ordinal.items():
                if marker in n:
                    q.entity_id=self.retriever.entity_by_ordinal(q.entity_type,index)
                    q.reference=f"ordinal:{index}"
                    break
        if re.search(r"(?:همکار|دوست)(?:م|ام)?",n) and any(x in n for x in ("اسم","نام")):
            q.entity_type="person"; q.relation="name"
            role="colleague" if "همکار" in n else "friend"
            q.reference=role
            q.entity_id=self.retriever.related_entity(role)
        if any(x in n for x in ("برای چی بود","برای چه بود","کارش چی بود","هدفش چی بود")) and (q.entity_id or typ):
            q.relation="purpose"; q.entity_type=q.entity_type or typ
        preference_context=(
            "قهوه" in n or "ترجیح" in n or
            bool(re.search(r"دوست\s+(?:دارم|داری|داشتم|داشتی|دارد|داریم)",n,re.I))
        )
        if (not q.relation and preference_context and
                any(x in n for x in ("چطوری","چگونه","چه جوری","چی","یادم"))):
            q.subject="user"; q.relation="preference"; q.value_hint="قهوه" if "قهوه" in n else ""
        if re.search(r"(?:منظورم|منظورت)\s+(?:اسم|نام)\s+",n):
            q.relation="name"; q.entity_type=typ
        if q.entity_type and not q.entity_id:
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
        # Only assertive/corrective utterances can create durable semantic facts.
        # Questions, commands, speculation and uncertainty are context, never facts.
        if utterance in {"statement","preference","correction"}:
            a,b=self._extract_named_entity(text,linguistic,slots,source_turn); entities+=a; facts+=b
            if not b:
                a,b=self._token_frame(linguistic,slots,source_turn); entities+=a; facts+=b
            a,b=self._extract_person(text,slots,source_turn); entities+=a; facts+=b
            if utterance in {"preference","statement"}:
                facts+=self._extract_preference(text,source_turn)
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

    def _rank_evidence(self,turn):
        return self.retriever.rank(turn.query)

    def answer(self,turn):
        evidence=self._rank_evidence(turn); turn.evidence=evidence
        q=turn.query
        # A resolved entity reference is a hard semantic filter, not merely a
        # ranking hint. This prevents a high-scoring fact from another entity
        # of the same type from becoming the answer.
        active=next((x for x in evidence
                     if not x.superseded and
                     (not q.entity_id or str(x.subject)==str(q.entity_id))),None)
        if not active:return ""
        if q.relation=="name":
            label=self.TYPE_LABELS.get(q.entity_type or active.entity_type,"مورد")
            turn.semantic_answer=f"اسم {label} «{active.value}» است."
        elif q.relation=="purpose":
            label=self.TYPE_LABELS.get(q.entity_type or active.entity_type,"مورد")
            turn.semantic_answer=f"کاربرد ثبت‌شده برای {label} «{active.value}» است."
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
        import difflib
        near_question = (
            any(x in q for x in self.QUESTION_MARKERS)
            and difflib.SequenceMatcher(None,q,a).ratio() >= .92
        )
        previous_echo=False
        for row in recent_user_turns or []:
            r=normalize_fa(row)
            # A legitimate reference answer may quote the prior question as
            # context ("موضوع قبلی ..."). Block only when the prior question is
            # effectively the answer itself, not merely cited inside an answer.
            if len(r)>8 and any(x in r for x in self.QUESTION_MARKERS):
                ratio=difflib.SequenceMatcher(None,r,a).ratio()
                if a.strip(" «»'\".")==r.strip(" «»'\".") or ratio>=.90:
                    previous_echo=True;break
        if exact or near_question or previous_echo:
            if semantic_answer:
                return semantic_answer,True,"semantic_fact_repair"
            if any(x in q for x in self.QUESTION_MARKERS):
                return "UNKNOWN: پاسخ قابل اتکا از factهای معنایی موجود پیدا نکردم؛ متن خام گفتگو را به‌عنوان جواب برنمی‌گردانم.",True,"question_echo_blocked"
            return "متوجه شدم؛ این پیام به‌عنوان زمینه مکالمه ثبت شد و متن خودت را به‌عنوان پاسخ تکرار نمی‌کنم.",True,"statement_echo_blocked"
        return answer,False,""

    def backend_status(self):
        return {
            "active":getattr(self.linguistic,"last_backend","iran_fallback"),
            "optional":dict(self.linguistic.optional),
            "last_backend_error":getattr(self.linguistic,"last_backend_error",""),
            "runtime_downloads":False,
            "offline":True,
            "decision_owner":"CognitiveSystem",
        }
