from dataclasses import dataclass,asdict
from datetime import datetime
import json
from pathlib import Path

@dataclass
class Entity:
    id:str;type:str;name:str;attributes:dict;updated_at:str
@dataclass
class Relation:
    source:str;relation:str;target:str;confidence:float=1.;source_kind:str='local'

class WorldModel:
    """Temporal local world model with entities, relations, state changes, events and causal edges."""
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.entities={};self.relations=[];self.events=[];self.observations=[];self.transitions=[];self._load()
    def _load(self):
        if not self.path.exists():return
        try:
            d=json.loads(self.path.read_text(encoding='utf-8'));self.entities=d.get('entities',{});self.relations=d.get('relations',[]);self.events=d.get('events',[])[-2000:];self.observations=d.get('observations',[])[-2000:];self.transitions=d.get('transitions',[])[-2000:]
        except Exception:self.entities,self.relations,self.events,self.observations,self.transitions={},{},[],[],[]
    def _save(self):
        d={'entities':self.entities,'relations':self.relations,'events':self.events[-2000:],'observations':self.observations[-2000:],'transitions':self.transitions[-2000:]};tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(self.path)
    def upsert_entity(self,entity_id,entity_type,name,attributes=None):
        now=datetime.now().isoformat(timespec='seconds');cur=self.entities.get(entity_id,{});attrs=dict(cur.get('attributes',{}));attrs.update(attributes or {});self.entities[entity_id]=asdict(Entity(entity_id,entity_type,name,attrs,now));self._save();return self.entities[entity_id]
    def relate(self,source,relation,target,confidence=1.,source_kind='local'):
        item=asdict(Relation(source,relation,target,float(confidence),source_kind))
        for old in self.relations:
            if old['source']==source and old['relation']==relation and old['target']==target:old['confidence']=max(old.get('confidence',0),item['confidence']);self._save();return old
        self.relations.append(item);self._save();return item
    def transition(self,state,action,result,confidence=.7):
        item={'time':datetime.now().isoformat(timespec='seconds'),'state':state,'action':action,'result':result,'confidence':float(confidence)};self.transitions.append(item);self._save();return item
    def record_observation(self,kind,value,confidence=.7,source='local'):
        item={'time':datetime.now().isoformat(timespec='seconds'),'kind':str(kind),'value':value,'confidence':float(confidence),'source':source};self.observations.append(item);self.observations=self.observations[-2000:];self._save();return item
    def record_event(self,event_type,data):
        self.events.append({'time':datetime.now().isoformat(timespec='seconds'),'type':event_type,'data':data});self.events=self.events[-2000:];self._save()
    def neighbors(self,entity_id):return [('out',r) for r in self.relations if r['source']==entity_id]+[('in',r) for r in self.relations if r['target']==entity_id]
    def query(self,term,limit=20):
        t=str(term).lower();rows=[]
        for eid,e in self.entities.items():
            if t in json.dumps(e,ensure_ascii=False).lower():rows.append(('entity',eid,e))
        for r in self.relations:
            if t in json.dumps(r,ensure_ascii=False).lower():rows.append(('relation',None,r))
        return rows[:int(limit)]
    def recent_transitions(self,limit=20):return self.transitions[-int(limit):]
    def snapshot(self):return {'entities':len(self.entities),'relations':len(self.relations),'events':len(self.events),'observations':len(self.observations),'transitions':len(self.transitions)}


    def causal_relation(self,cause,effect,confidence=.6,source='local'):
        item={'cause':str(cause),'effect':str(effect),'confidence':float(confidence),'source':source,
              'time':datetime.now().isoformat(timespec='seconds')}
        self.relations.append({'source':str(cause),'relation':'causes','target':str(effect),
                               'confidence':float(confidence),'source_kind':source});self._save();return item

    def state_at(self,kind,limit=20):
        rows=[x for x in self.observations if x.get('kind')==kind]
        return rows[-int(limit):]

    def infer(self,term,limit=10):
        """Traverse local relations two hops to expose indirectly related state."""
        start=str(term);direct=[];second=[]
        for r in self.relations:
            if r.get('source')==start or r.get('target')==start: direct.append(r)
        mids={r.get('target') for r in direct if r.get('source')==start}|{r.get('source') for r in direct if r.get('target')==start}
        for r in self.relations:
            if r.get('source') in mids or r.get('target') in mids: second.append(r)
        return {'direct':direct[-int(limit):],'two_hop':second[-int(limit):]}

    def temporal_summary(self,limit=20):
        return {'observations':self.observations[-int(limit):],'transitions':self.transitions[-int(limit):],
                'events':self.events[-int(limit):]}

# v0.22: state-aware world reasoning and temporal confidence.
def _infer_v2(self,term,limit=12):
    start=str(term); direct=[]; second=[]
    for r in self.relations:
        if r.get('source')==start or r.get('target')==start: direct.append(r)
    mids={r.get('target') for r in direct if r.get('source')==start}|{r.get('source') for r in direct if r.get('target')==start}
    for r in self.relations:
        if r.get('source') in mids or r.get('target') in mids: second.append(r)
    direct=sorted(direct,key=lambda x:float(x.get('confidence',0)),reverse=True)[:int(limit)]
    second=sorted(second,key=lambda x:float(x.get('confidence',0)),reverse=True)[:int(limit)]
    return {'direct':direct,'two_hop':second,'confidence':round(max([float(x.get('confidence',0)) for x in direct] or [0]),3)}
WorldModel.infer=_infer_v2

def _state_summary(self,kind,limit=20):
    rows=self.state_at(kind,limit); return {'kind':kind,'count':len(rows),'latest':rows[-1] if rows else None,'history':rows}
WorldModel.state_summary=_state_summary
