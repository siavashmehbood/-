import json
from pathlib import Path
from datetime import datetime

class KnowledgeGraph:
    """Local durable knowledge graph with confidence, provenance and contradiction tracking."""
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.facts=[]; self._load()

    def _load(self):
        if self.path.exists():
            try:self.facts=json.loads(self.path.read_text(encoding='utf-8'))
            except Exception:self.facts=[]

    def _save(self):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(self.facts,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.path)

    def add_fact(self,subject,predicate,object_,confidence=1.0,source='internal'):
        fact={'subject':str(subject),'predicate':str(predicate),'object':str(object_),'confidence':float(confidence),'source':str(source),'updated_at':datetime.now().isoformat(timespec='seconds')}
        for old in self.facts:
            if old['subject']==fact['subject'] and old['predicate']==fact['predicate'] and old['object']==fact['object']:
                old.update({'confidence':max(old.get('confidence',0),fact['confidence']),'updated_at':fact['updated_at']}); self._save(); return old
        self.facts.append(fact); self._save(); return fact

    def contradict(self,subject,predicate,object_,confidence=.7,source='internal'):
        for fact in self.facts:
            if fact['subject']==str(subject) and fact['predicate']==str(predicate) and fact['object']!=str(object_):
                fact['contradicted_by']={'object':str(object_),'confidence':float(confidence),'source':str(source)}
        return self.add_fact(subject,predicate,object_,confidence,source)

    def query(self,term,limit=20):
        t=str(term).lower(); return [f for f in self.facts if t in ' '.join(str(v).lower() for v in f.values())][:int(limit)]

    def related(self,subject,limit=20): return [f for f in self.facts if f['subject']==str(subject)][:int(limit)]
    def stats(self): return {'facts':len(self.facts),'contradictions':sum('contradicted_by' in f for f in self.facts)}


    def infer(self,subject,depth=2,limit=30):
        """Local multi-hop traversal with confidence propagation."""
        frontier=[(str(subject),1.0,0)];seen=set();out=[]
        while frontier:
            node,conf,level=frontier.pop(0)
            if level>=int(depth): continue
            for fact in self.facts:
                if fact.get('subject')!=node: continue
                key=(fact.get('subject'),fact.get('predicate'),fact.get('object'))
                if key in seen: continue
                seen.add(key);score=conf*float(fact.get('confidence',0))
                out.append({'fact':fact,'inferred_confidence':round(score,4),'hop':level+1})
                frontier.append((str(fact.get('object')),score,level+1))
        return sorted(out,key=lambda x:x['inferred_confidence'],reverse=True)[:int(limit)]

    def contradictions(self,subject=None):
        rows=[f for f in self.facts if 'contradicted_by' in f]
        if subject is not None: rows=[f for f in rows if f.get('subject')==str(subject)]
        return rows

    def best_fact(self,subject,predicate):
        rows=[f for f in self.facts if f.get('subject')==str(subject) and f.get('predicate')==str(predicate)]
        return max(rows,key=lambda x:float(x.get('confidence',0)),default=None)

# v0.22: contradiction-aware retrieval and confidence-weighted inference.
def _query_v2(self,term,limit=20):
    t=str(term).lower(); rows=[]
    for f in self.facts:
        text=' '.join(str(f.get(k,'')) for k in ('subject','predicate','object','source')).lower()
        if t in text:
            penalty=.20 if 'contradicted_by' in f else 0
            rows.append((float(f.get('confidence',0))-penalty,f))
    return [f for _,f in sorted(rows,key=lambda x:x[0],reverse=True)[:int(limit)]]

def _resolve(self,subject,predicate):
    rows=[f for f in self.facts if f.get('subject')==str(subject) and f.get('predicate')==str(predicate)]
    if not rows:return None
    ranked=[]
    for f in rows:
        score=float(f.get('confidence',0))*(.65 if 'contradicted_by' not in f else .35)
        ranked.append((score,f))
    return max(ranked,key=lambda x:x[0])[1]
KnowledgeGraph.query=_query_v2
KnowledgeGraph.resolve=_resolve


# v0.29 Task C: typed memory graph over the existing durable fact graph.
def _add_node(self, node_id, node_type, data=None, confidence=1.0, source='internal'):
    return self.add_fact('node:'+str(node_id), 'type', str(node_type), confidence, source) if not data else self.add_fact('node:'+str(node_id), 'data', json.dumps(data, ensure_ascii=False, sort_keys=True), confidence, source)

def _add_edge(self, source_id, relation, target_id, confidence=1.0, provenance='internal', source='internal'):
    row=self.add_fact('node:'+str(source_id), str(relation), 'node:'+str(target_id), confidence, source)
    row['provenance']=str(provenance); row['timestamp']=row.get('updated_at'); self._save(); return row

def _neighbors(self, node_id, relation=None, limit=50):
    sid='node:'+str(node_id); rows=[]
    for f in self.facts:
        if f.get('subject')!=sid: continue
        if relation and f.get('predicate')!=str(relation): continue
        rows.append(f)
    return rows[:int(limit)]

def _graph_query(self, node_id, depth=3, limit=100):
    frontier=[(str(node_id),0)]; seen=set(); out=[]
    while frontier and len(out)<int(limit):
        node,level=frontier.pop(0)
        if level>=int(depth): continue
        for edge in self.neighbors(node):
            key=(edge.get('subject'),edge.get('predicate'),edge.get('object'))
            if key in seen: continue
            seen.add(key); out.append({'edge':edge,'hop':level+1})
            target=str(edge.get('object','')).replace('node:','',1); frontier.append((target,level+1))
    return out

KnowledgeGraph.add_node=_add_node
KnowledgeGraph.add_edge=_add_edge
KnowledgeGraph.neighbors=_neighbors
KnowledgeGraph.graph_query=_graph_query


# v0.29b: ensure every graph node has an explicit type plus optional payload.
def _add_node_v2(self, node_id, node_type, data=None, confidence=1.0, source='internal'):
    self.add_fact('node:'+str(node_id), 'type', str(node_type), confidence, source)
    if data is not None:
        self.add_fact('node:'+str(node_id), 'data', json.dumps(data, ensure_ascii=False, sort_keys=True), confidence, source)
    return self.best_fact('node:'+str(node_id), 'type')
KnowledgeGraph.add_node = _add_node_v2


# v0.29c: adding a competing fact records the contradiction durably.
if not hasattr(KnowledgeGraph, '_taskc_base_add_fact'):
    KnowledgeGraph._taskc_base_add_fact = KnowledgeGraph.add_fact
_old_add_fact_taskc = KnowledgeGraph._taskc_base_add_fact

def _add_fact_taskc(self, subject, predicate, object_, confidence=1.0, source='internal'):
    s,p,o=str(subject),str(predicate),str(object_)
    for old in self.facts:
        if old.get('subject')==s and old.get('predicate')==p and old.get('object')!=o:
            old['contradicted_by']={'object':o,'confidence':float(confidence),'source':str(source),'timestamp':datetime.now().isoformat(timespec='seconds')}
    row=_old_add_fact_taskc(self,subject,predicate,object_,confidence,source)
    self._save()
    return row
KnowledgeGraph.add_fact=_add_fact_taskc
