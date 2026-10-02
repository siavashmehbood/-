"""Rasa-inspired conversation foundation adapter for IRAN.

Design provenance: independently implemented from the public Rasa OSS 3.6.x
event/tracker contracts (Apache-2.0). No Rasa source code is copied. Rasa dialogue
policies are intentionally not used: CognitiveSystem remains the sole decision owner.
"""
from dataclasses import dataclass,field,asdict
from typing import Any
import time, json
from pathlib import Path

@dataclass(frozen=True)
class ConversationEvent:
    type:str
    data:dict=field(default_factory=dict)
    timestamp:float=0.0
    source:str="iran"
    def to_dict(self): return asdict(self)

@dataclass
class FoundationState:
    slots:dict=field(default_factory=dict)
    latest_message:dict=field(default_factory=dict)
    active_loop:str=""
    previous_action:str=""
    events:list=field(default_factory=list)

class RasaFoundationAdapter:
    """Foundation semantics only: NLU contract, slots and replayable events.

    It never selects an answer, tool, policy or next action.
    """
    SOURCE="RasaHQ/rasa 3.6.x concepts"
    LICENSE="Apache-2.0"
    def __init__(self,max_events=120,path=None):
        self.max_events=max(10,int(max_events)); self.path=Path(path) if path else None; self.state=FoundationState()
        if self.path and self.path.exists():
            try:self.state=self.replay(json.loads(self.path.read_text(encoding="utf-8")),self.max_events).state
            except (OSError,ValueError,TypeError):pass
    def ingest(self,meaning:Any,parsed:dict|None=None):
        parsed=parsed or {}
        intent={"name":getattr(meaning,"dialogue_act","unknown"),
                "confidence":float(getattr(meaning,"confidence",0.0))}
        entities=list(getattr(meaning,"entities",[]) or parsed.get("entities") or [])
        msg={"text":getattr(meaning,"normalized_text",""),"intent":intent,"entities":entities,
             "ambiguity":float(getattr(meaning,"ambiguity",0.0))}
        self.state.latest_message=msg
        self._event("user",msg)
        topic=getattr(meaning,"topic","")
        if topic:self.set_slot("topic",topic)
        requested=getattr(meaning,"requested_action","")
        if requested:self.set_slot("requested_action",requested)
        return msg
    def set_slot(self,name,value):
        if value in ("",None):self.state.slots.pop(name,None)
        else:self.state.slots[str(name)]=value
        self._event("slot",{"name":str(name),"value":value})
    def record_outcome(self,answer_type:str,verification:str):
        self.state.previous_action=str(answer_type or "")
        self._event("assistant_outcome",{"answer_type":answer_type,"verification":verification})
    def _event(self,event_type,data):
        self.state.events.append({"type":event_type,"data":dict(data),"source":"iran"})
        self.state.events=self.state.events[-self.max_events:]
    def save(self):
        if not self.path:return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.state.events,ensure_ascii=False),encoding="utf-8"); tmp.replace(self.path)
    def current_state(self):
        return {"slots":dict(self.state.slots),"latest_message":dict(self.state.latest_message),
                "active_loop":self.state.active_loop,"previous_action":self.state.previous_action,
                "events":list(self.state.events)}
    @classmethod
    def replay(cls,events,max_events=120):
        obj=cls(max_events)
        for raw in list(events or [])[-max_events:]:
            typ=raw.get("type"); data=dict(raw.get("data") or {})
            if typ=="slot":
                name=data.get("name"); value=data.get("value")
                if name:
                    if value in ("",None):obj.state.slots.pop(name,None)
                    else:obj.state.slots[name]=value
            elif typ=="user":obj.state.latest_message=data
            elif typ=="assistant_outcome":obj.state.previous_action=str(data.get("answer_type",""))
            obj.state.events.append(dict(raw))
        return obj
