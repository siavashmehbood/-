"""Unified input/ingestion fabric for IRAN."""
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import hashlib, json, re, uuid

@dataclass
class InputEvent:
    event_id: str
    source: str
    input_type: str
    content: str
    domain: str
    timestamp: str
    provenance: dict
    confidence: float = 0.0
    cycle_id: str = ""

class InputFabric:
    SOURCES={"user","web","document","code","execution","feedback","memory","self_experiment","system"}
    TYPES={"conversation","document","web_page","code","execution_result","correction","feedback","question","knowledge","observation","other"}
    DOMAINS={
      "programming":("python","پایتون","کد","برنامه","تابع","حلقه","الگوریتم","javascript","java","c++"),
      "computer_science":("علوم کامپیوتر","ساختمان داده","پایگاه داده","سیستم عامل","شبکه","امنیت"),
      "artificial_intelligence":("هوش مصنوعی","یادگیری ماشین","یادگیری عمیق","شبکه عصبی","پردازش زبان","ai","machine learning"),
      "mathematics":("ریاضی","معادله","جبر","هندسه","حسابان","احتمال","آمار","منطق","math"),
      "physics":("فیزیک","نیرو","حرکت","انرژی","الکتریسیته","مغناطیس"),
      "chemistry":("شیمی","اتم","مولکول","واکنش","عنصر"),
      "biology":("زیست","سلول","ژن","ژنتیک","تکامل"),
      "persian_literature":("ادبیات فارسی","فارسی","غزل","مثنوی","شاهنامه","حافظ","سعدی"),
      "english":("انگلیسی","english","grammar","vocabulary","لغت","گرامر","reading","writing"),
      "law":("حقوق","قانون","قرارداد","جرم","مدنی","کیفری"),
    }
    def __init__(self,root,runtime=None,max_events=10000):
        self.root=Path(root); self.runtime=runtime; self.max_events=int(max_events)
        self.path=self.root/"data"/"input_fabric.json"; self.events=[]; self.seen=set()
        self.stats_data={"ingested":0,"duplicates":0,"units":0,"domains":{},"sources":{}}
        self._load()
    def _load(self):
        try:
            p=json.loads(self.path.read_text(encoding="utf-8"))
            self.events=(p.get("events",[]) if isinstance(p,dict) else [])[-self.max_events:]
            self.seen={self._key(r.get("source",""),r.get("input_type",""),r.get("content","")) for r in self.events}
            if isinstance(p,dict): self.stats_data.update(p.get("stats",{}))
        except Exception: self.events=[]; self.seen=set()
    def _save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload={"version":1,"events":self.events[-self.max_events:],"stats":self.stats_data}
        tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(self.path)
    @staticmethod
    def normalize(content):
        return re.sub(r"[ \t]+"," ",str(content or "").replace("\r\n","\n").replace("\r","\n")).strip()
    @staticmethod
    def _key(source,input_type,content):
        return hashlib.sha256(f"{source}|{input_type}|{InputFabric.normalize(content).lower()}".encode("utf-8")).hexdigest()[:24]
    @classmethod
    def detect_domain(cls,content,supplied=""):
        if supplied:return str(supplied)
        text=str(content).lower()
        scores={d:sum(1 for w in words if w in text) for d,words in cls.DOMAINS.items()}
        best=max(scores,key=scores.get) if scores else "general"
        return best if scores.get(best,0) else "general"
    @staticmethod
    def extract_units(content, source="user", input_type="conversation"):
        text=InputFabric.normalize(content)
        if not text:
            return []
        units=[]
        correction_re=r"^(نه|اشتباه|اصلاح|درستش|غلط|تصحیح|تصحيح|اصلاح کن|درست کن)\b"
        if input_type=="correction" or re.match(correction_re,text,re.I):
            units.append({"kind":"correction","content":text,"reusable":True})
        if "؟" in text or "?" in text or re.match(r"^(آیا|چرا|چطور|چگونه|کدام|کی|چه|مگر|ممکن است)\b",text):
            units.append({"kind":"question","content":text,"reusable":False})
        if input_type=="code" or "CODEBLOCK" in text or re.search(r"\b(def|class|import|for|while|return|function|const|let)\b",text):
            units.append({"kind":"procedure_candidate","content":text,"reusable":True})
        sentences=[x.strip() for x in re.split(r"(?<=[.!؟?])\s+|\n+",text) if x.strip()]
        if not sentences:
            sentences=[text]
        claim_markers=(" است "," هست "," هستند "," یعنی "," شامل "," برابر "," به‌عنوان "," به عنوان "," باعث "," می‌شود "," میشود "," می‌کند "," میکند "," دارد "," دارند "," باید "," نباید "," می‌توان "," میتوان "," تعریف "," روش ")
        for sentence in sentences:
            if len(sentence)<12 or "؟" in sentence or "?" in sentence:
                continue
            padded=" "+sentence+" "
            declarative=input_type in {"knowledge","document","web_page","feedback","correction"} or any(m in padded for m in claim_markers)
            if declarative:
                units.append({"kind":"claim_candidate","content":sentence,"reusable":True})
        if not units:
            units.append({"kind":"observation","content":text,"reusable":False})
        out=[]; seen=set()
        for unit in units:
            key=(unit["kind"],re.sub(r"\s+"," ",unit["content"]).strip().lower())
            if key not in seen:
                seen.add(key); out.append(unit)
        return out[:32]

    def ingest(self,content,source="user",input_type="conversation",domain="",provenance=None,confidence=0.0,cycle_id="",create_goal=True):
        content=self.normalize(content); source=str(source or "user"); input_type=str(input_type or "other")
        if source not in self.SOURCES:source="system"
        if input_type not in self.TYPES:input_type="other"
        if not content:return {"ok":False,"reason":"empty_input"}
        key=self._key(source,input_type,content)
        if key in self.seen:
            self.stats_data["duplicates"]=int(self.stats_data.get("duplicates",0))+1
            return {"ok":True,"duplicate":True,"key":key,"units":[]}
        event=InputEvent("inp-"+uuid.uuid4().hex[:12],source,input_type,content[:30000],self.detect_domain(content,domain),datetime.now().isoformat(timespec="seconds"),dict(provenance or {}),max(0,min(1,float(confidence or 0))),str(cycle_id or ""))
        units=self.extract_units(content,source,input_type); payload=asdict(event); payload["units"]=units
        self.events.append(payload); self.events=self.events[-self.max_events:]; self.seen.add(key)
        self.stats_data["ingested"]=int(self.stats_data.get("ingested",0))+1
        self.stats_data["units"]=int(self.stats_data.get("units",0))+len(units)
        self.stats_data.setdefault("domains",{})[event.domain]=int(self.stats_data.get("domains",{}).get(event.domain,0))+1
        self.stats_data.setdefault("sources",{})[source]=int(self.stats_data.get("sources",{}).get(source,0))+1
        self._save()
        learning_candidates=[u for u in units if u.get("reusable") and u.get("kind") in {"correction","claim_candidate","procedure_candidate"}]
        learning_results=[]
        if self.runtime is not None and learning_candidates:
            for unit in learning_candidates:
                try:
                    learning_results.append(self.runtime.learning.record(
                        goal=f"learn_from_input:{event.domain}",
                        action=f"input_{unit["kind"]}",
                        result=unit["content"],
                        score=max(0.75, event.confidence or 0.75),
                        intent="input_candidate",
                        strategy="input_fabric",
                        domain=event.domain,
                        objective=f"turn reusable {unit["kind"]} input into a reviewable learning candidate",
                        expected_effect="the same or similar future input should be handled with this reusable evidence",
                        signal_source=f"input:{source}",
                        evidence=event.event_id,
                    ))
                except Exception:
                    pass
        if self.runtime is not None:
            try:self.runtime.events.emit("input_ingested",{"event_id":event.event_id,"source":source,"input_type":input_type,"domain":event.domain,"units":len(units)})
            except Exception:pass
            if create_goal and event.domain!="general":
                try:self.runtime.self_directed_learning.create_goal(content[:160],"input_requires_grounded_processing",f"extract_and_verify:{content[:160]}","medium",event.domain)
                except Exception:pass
        return {"ok":True,"duplicate":False,"event":payload,"units":units,"learning":learning_results}
    def ingest_batch(self,items,create_goal=True):
        results=[]
        for item in items or []:
            if isinstance(item,dict):
                results.append(self.ingest(item.get("content",""),item.get("source","system"),item.get("input_type","other"),item.get("domain",""),item.get("provenance"),item.get("confidence",0),item.get("cycle_id",""),create_goal))
            else:results.append(self.ingest(item,create_goal=create_goal))
        return {"ok":True,"processed":len(results),"new":sum(not r.get("duplicate",False) and r.get("ok") for r in results),"results":results}
    def stats(self):return {"events":len(self.events),**self.stats_data}
    def recent(self,limit=20,source=None,domain=None):
        rows=self.events
        if source:rows=[r for r in rows if r.get("source")==source]
        if domain:rows=[r for r in rows if r.get("domain")==domain]
        return rows[-int(limit):]
