import sqlite3,math,re
from pathlib import Path
from datetime import datetime

class Memory:
    """Durable local memory: episodic traces, semantic facts and procedural lessons."""
    def __init__(self,db_path,gate=None):
        self.gate=gate
        path=Path(db_path); path.parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(path,check_same_thread=False)
        self.conn.execute('CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, kind TEXT, content TEXT, importance REAL DEFAULT 0.5, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        cols={r[1] for r in self.conn.execute('PRAGMA table_info(memories)').fetchall()}
        for n,d in [('importance','REAL DEFAULT 0.5'),('access_count','INTEGER DEFAULT 0'),('last_access','TEXT'),('confidence','REAL DEFAULT 0.5'),('source','TEXT DEFAULT "local"')]:
            if n not in cols:self.conn.execute(f'ALTER TABLE memories ADD COLUMN {n} {d}')
        self.conn.execute('CREATE TABLE IF NOT EXISTS semantic_facts (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, value TEXT, confidence REAL, source TEXT, created_at TEXT, updated_at TEXT, UNIQUE(subject,predicate,value))')
        self.conn.execute('CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, goal TEXT, lesson TEXT, confidence REAL, source TEXT, uses INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, UNIQUE(goal,lesson))')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_memory_kind ON memories(kind)'); self.conn.execute('CREATE INDEX IF NOT EXISTS idx_fact_subject ON semantic_facts(subject)'); self.conn.execute('CREATE INDEX IF NOT EXISTS idx_lesson_goal ON lessons(goal)'); self.conn.commit()
    def _tokens(self,text): return set(re.findall(r'[\wآ-ی]+',str(text).lower()))
    def _norm(self,text): return re.sub(r'\s+',' ',str(text).strip().replace('ي','ی').replace('ك','ک'))
    def add(self,kind,content,importance=.5,confidence=None,source='local'):
        content=self._norm(content)
        if not content:return None
        now=datetime.now().isoformat(timespec='seconds'); conf=float(importance if confidence is None else confidence)
        row=self.conn.execute('SELECT id FROM memories WHERE kind=? AND content=?',(str(kind),content)).fetchone()
        if row:
            self.conn.execute('UPDATE memories SET importance=MAX(importance,?),confidence=MAX(confidence,?),access_count=access_count+1,last_access=?,source=? WHERE id=?',(float(importance),conf,now,str(source),row[0])); self.conn.commit(); return row[0]
        cur=self.conn.execute('INSERT INTO memories(kind,content,importance,created_at,last_access,confidence,source) VALUES(?,?,?,?,?,?,?)',(str(kind),content,max(0,min(1,float(importance))),now,now,max(0,min(1,conf)),str(source))); self.conn.commit(); return cur.lastrowid
    def recent(self,limit=8): return list(reversed(self.conn.execute('SELECT kind,content,created_at FROM memories ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()))
    def search(self,query,limit=8,kind=None):
        query=self._norm(query)
        if not query:return self.recent(limit)
        q=self._tokens(query); rows=self.conn.execute('SELECT id,kind,content,importance,access_count,created_at,confidence FROM memories ORDER BY id DESC LIMIT 20000').fetchall(); now=datetime.now(); scored=[]
        for _,k,c,imp,access,created,conf in rows:
            if kind and k!=kind:continue
            toks=self._tokens(c); inter=q&toks
            if not inter:continue
            overlap=len(inter)/max(1,len(q)); phrase=float(query.lower() in c.lower())
            try:age=max(0,(now-datetime.fromisoformat(created)).total_seconds()/86400)
            except Exception:age=3650
            recency=math.exp(-age/90); usage=min(1,math.log1p(access or 0)/4)
            type_bonus=.08 if k in {'user','assistant','goal','fact','cognitive_state','semantic_fact','lesson'} else 0
            score=.38*overlap+.22*phrase+.13*float(imp)+.10*recency+.07*usage+.10*float(conf)+type_bonus
            scored.append((score,(k,c,created)))
        scored.sort(key=lambda x:x[0],reverse=True); return [r for _,r in scored[:int(limit)]]
    def working_context(self,query,limit=12):
        rows=self.search(query,max(8,limit)); recent=self.recent(limit); out=[]; seen=set()
        for row in rows+recent:
            key=(row[0],row[1])
            if key not in seen and row[1] not in {'','{}'}: seen.add(key); out.append(row)
            if len(out)>=limit:break
        return out
    def add_semantic_fact(self,subject,predicate,value,confidence=.65,source='inference'):
        now=datetime.now().isoformat(timespec='seconds'); s=self._norm(subject); p=self._norm(predicate); v=self._norm(value)
        if self.gate is not None:
            payload={'subject':s,'predicate':p,'value':v,'confidence':float(confidence),'source':str(source)}
            proposal=self.gate.request('memory.add_semantic_fact',payload,f'Semantic fact: {s} / {p} / {v}')
            if proposal is not None: return proposal
        row=self.conn.execute('SELECT id,confidence FROM semantic_facts WHERE subject=? AND predicate=? AND value=?',(s,p,v)).fetchone()
        if row:
            self.conn.execute('UPDATE semantic_facts SET confidence=MAX(confidence,?),source=?,updated_at=? WHERE id=?',(float(confidence),str(source),now,row[0])); self.conn.commit(); return row[0]
        cur=self.conn.execute('INSERT INTO semantic_facts(subject,predicate,value,confidence,source,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(s,p,v,float(confidence),str(source),now,now)); self.conn.commit(); return cur.lastrowid
    def semantic_search(self,query,limit=8):
        q=self._tokens(query); rows=self.conn.execute('SELECT subject,predicate,value,confidence,source,updated_at FROM semantic_facts').fetchall(); scored=[]
        for s,p,v,c,src,updated in rows:
            text=f'{s} {p} {v}'; inter=q&self._tokens(text)
            if not inter:continue
            score=.65*len(inter)/max(1,len(q))+.35*float(c)
            scored.append((score,{'subject':s,'predicate':p,'value':v,'confidence':c,'source':src,'updated_at':updated}))
        return [x[1] for x in sorted(scored,key=lambda x:x[0],reverse=True)[:int(limit)]]
    def add_lesson(self,goal,lesson,confidence=.6,source='experience'):
        now=datetime.now().isoformat(timespec='seconds'); g=self._norm(goal); l=self._norm(lesson)
        if self.gate is not None:
            payload={'goal':g,'lesson':l,'confidence':float(confidence),'source':str(source)}
            proposal=self.gate.request('memory.add_lesson',payload,f'Lesson: {g}')
            if proposal is not None: return proposal
        row=self.conn.execute('SELECT id,uses FROM lessons WHERE goal=? AND lesson=?',(g,l)).fetchone()
        if row:
            self.conn.execute('UPDATE lessons SET confidence=MAX(confidence,?),uses=uses+1,source=?,updated_at=? WHERE id=?',(float(confidence),str(source),now,row[0])); self.conn.commit(); return row[0]
        cur=self.conn.execute('INSERT INTO lessons(goal,lesson,confidence,source,uses,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(g,l,float(confidence),str(source),1,now,now)); self.conn.commit(); return cur.lastrowid
    def lesson_search(self,goal,limit=8):
        q=self._tokens(goal); rows=self.conn.execute('SELECT goal,lesson,confidence,source,uses,updated_at FROM lessons').fetchall(); scored=[]
        for g,l,c,src,uses,updated in rows:
            inter=q&self._tokens(g+' '+l)
            if not inter:continue
            score=.65*len(inter)/max(1,len(q))+.2*float(c)+.15*min(1,math.log1p(uses)/4); scored.append((score,{'goal':g,'lesson':l,'confidence':c,'source':src,'uses':uses,'updated_at':updated}))
        return [x[1] for x in sorted(scored,key=lambda x:x[0],reverse=True)[:int(limit)]]
    def semantic_stats(self):
        return {'facts':self.conn.execute('SELECT COUNT(*) FROM semantic_facts').fetchone()[0],'lessons':self.conn.execute('SELECT COUNT(*) FROM lessons').fetchone()[0]}
    def decay(self,days=120):
        cutoff=datetime.now().timestamp()-int(days)*86400
        rows=self.conn.execute('SELECT id,created_at,importance FROM memories').fetchall(); changed=0
        for i,created,imp in rows:
            try:age=(datetime.now()-datetime.fromisoformat(created)).total_seconds()/86400
            except Exception:continue
            if age>days and float(imp)<.75:
                self.conn.execute('UPDATE memories SET importance=MAX(.05,importance*.90) WHERE id=?',(i,)); changed+=1
        self.conn.commit(); return {'decayed':changed,'days':days}
    def stats(self):
        return {'memories':self.conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0],**self.semantic_stats()}
    def close(self):
        try:self.conn.commit(); self.conn.close()
        except Exception:pass
    def __enter__(self): return self
    def __exit__(self,*args): self.close()

# v0.23b: suppress self-referential response scaffolding from recall.
_META_PREFIXES=('برای این مرجع،','نزدیک‌ترین خاطرات مرتبط،','حافظه مرتبط:','برداشت من از سؤال:')
_old_search=Memory.search
def _search_v2(self,query,limit=8,kind=None):
    rows=_old_search(self,query,max(12,int(limit)*3),kind)
    clean=[]
    for row in rows:
        content=str(row[1])
        if content.startswith(_META_PREFIXES):continue
        if content==self._norm(query):continue
        if row not in clean:clean.append(row)
        if len(clean)>=int(limit):break
    return clean
Memory.search=_search_v2
