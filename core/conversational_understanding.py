"""General local conversational understanding for the canonical IRAN brain.

This module does not answer users. It represents utterance meaning so CognitiveSystem's
existing pipeline can reason, plan, generate and verify without treating every turn as a
fact question.
"""
from dataclasses import dataclass,asdict,field
import re

@dataclass
class UtteranceMeaning:
    raw_text:str
    normalized_text:str
    language:str="unknown"
    dialogue_act:str="unknown"
    intents:list=field(default_factory=list)
    entities:list=field(default_factory=list)
    references:list=field(default_factory=list)
    topic:str=""
    requested_action:str=""
    requested_answer_type:str=""
    ambiguity:float=0.0
    confidence:float=0.0
    tone_cues:list=field(default_factory=list)
    temporal:list=field(default_factory=list)
    incomplete:bool=False
    def to_dict(self): return asdict(self)

class ConversationalUnderstanding:
    """Small deterministic mechanics layer; classifications feed cognition, never bypass it."""
    SOCIAL={"سلام":"greeting","درود":"greeting","خداحافظ":"farewell","مرسی":"gratitude","ممنون":"gratitude",
            "ببخشید":"apology","باشه":"acknowledgement","اوکی":"acknowledgement"}
    FOLLOW={"چرا":"explanation_request","چطور":"follow_up","چگونه":"follow_up","بعدش":"continuation",
            "ادامه بده":"continuation","مثال بزن":"example_request","یعنی چی":"clarification",
            "ساده تر بگو":"simplify","ساده‌تر بگو":"simplify","کوتاه بگو":"length_control",
            "کامل توضیح بده":"length_control"}
    def __init__(self,language_engine=None): self.language_engine=language_engine
    def normalize(self,text):
        t=str(text or "").strip().replace("ي","ی").replace("ك","ک")
        t=re.sub(r"\s+"," ",t)
        # meaning-preserving colloquial canonicalization, not response selection
        forms=((r"\bمیخام\b","می‌خواهم"),(r"\bمیخوام\b","می‌خواهم"),(r"\bمی خواهم\b","می‌خواهم"),
               (r"\bنمیدونم\b","نمی‌دانم"),(r"\bنمی دونم\b","نمی‌دانم"),(r"\bچجوری\b","چطور"))
        for pattern,value in forms:t=re.sub(pattern,value,t)
        return t
    def analyze(self,text,state=None,parsed=None):
        raw=str(text or ""); norm=self.normalize(raw); bare=norm.rstrip("؟?!., ").strip(); low=bare.lower()
        parsed=parsed or {}; act="unknown"; answer_type=""
        for marker,label in self.SOCIAL.items():
            if low==marker or low.startswith(marker+" "):act=label; break
        if act=="unknown":
            for marker,label in self.FOLLOW.items():
                if low==marker or low.startswith(marker+" "):act=label; break
        if act=="unknown" and re.match(r"^(نه|منظورم|اشتباه فهمیدی|نه منظورم)",low):act="correction"
        if act=="unknown" and any(x in low for x in ("برگردیم","برگرد بحث","بحث قبلی","موضوع قبلی")):act="return_to_topic"
        if act=="unknown" and any(x in low for x in ("فرق ","تفاوت ","مقایسه")):act="comparison"
        if act=="unknown" and any(x in low for x in ("مطمئنی","از کجا فهمیدی","چرا این جواب")):act="meta_conversation"
        if act=="unknown" and any(x in low for x in ("باز کن","ببند","اجرا کن","بنویس","کلیک","اسکرین")):act="tool_request"
        if act=="unknown" and any(x in low for x in ("یاد بگیر","یادگیری","از صفر تا صد یاد","می‌خواهم یاد بگیر","میخوام یاد بگیر")):act="learning_request"
        if act=="unknown" and any(x in low for x in ("واقعیت","اطلاعات","بگو","توضیح بده")) and not any(x in low for x in ("همون","قبلی","ادامه","بیشتر")) and ("؟" not in norm and "?" not in norm):act="information_request"
        if act=="unknown" and ("؟" in norm or "?" in norm or any(low.startswith(x) for x in ("چرا","چی","چه ","کدام","کدوم","آیا","کی ","کجا"))):act="factual_question"
        if act=="unknown" and any(x in low for x in ("حوصله ندارم","خوشحالم","ناراحتم","خسته ام","خسته‌ام")):act="emotional_expression"
        if act=="unknown":act="casual_statement"
        answer_type={"explanation_request":"explanation","example_request":"example","simplify":"simpler",
                     "comparison":"comparison","tool_request":"action","learning_request":"learning","information_request":"information",
                     "greeting":"social","meta_conversation":"meta"}.get(act,"")
        refs=[x for x in ("این","اون","همون","قبلی","اولی","دومی","بعدی","این موضوع","اون برنامه") if x in low]
        incomplete=bool(len(bare.split())<=3 and act in {"follow_up","continuation","explanation_request","clarification","example_request","simplify"})
        language="unknown"
        if self.language_engine:
            try: language=self.language_engine.detect_language(norm)
            except Exception: pass
        confidence=.95 if act!="unknown" else .35
        ambiguity=.65 if refs and state is not None and not getattr(state,"current_topic","") and not getattr(state,"references",{}) else .15 if refs else 0.0
        return UtteranceMeaning(raw,norm,language,act,[parsed.get("intent","general")],
            list(parsed.get("entities") or []),refs,getattr(state,"current_topic","") if state else "",
            parsed.get("goal","") if act=="tool_request" else "",answer_type,ambiguity,confidence,
            [],list(parsed.get("temporal") or []),incomplete)
