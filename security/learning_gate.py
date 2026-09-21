"""Central human-approval gate for all durable learned knowledge."""
from __future__ import annotations
import hashlib, json, threading, re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from persistence import atomic_write_json, load_json_with_backup
import time
try:
    import msvcrt
except ImportError:
    msvcrt = None
try:
    import fcntl
except ImportError:
    fcntl = None

class LearningGate:
    """Single approval boundary for durable learning mutations."""
    def __init__(self, path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self._local=threading.local(); self._lock=threading.RLock()
        self._rows=load_json_with_backup(self.path,[])
        if not isinstance(self._rows,list): self._rows=[]

    @contextmanager
    def _process_lock(self):
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write("0")
                handle.flush()
            handle.seek(0)
            locked = False
            try:
                if msvcrt is not None:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    locked = True
                elif fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                    locked = True
                self._rows = load_json_with_backup(self.path, [])
                if not isinstance(self._rows, list):
                    self._rows = []
                yield
            finally:
                if locked:
                    try:
                        if msvcrt is not None:
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                        elif fcntl is not None:
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass

    @staticmethod
    def _learning_duplicate_key(kind, payload):
        if kind != 'learning.record_experience' or not isinstance(payload, dict):
            return None
        def norm(v):
            return re.sub(r'\s+', ' ', str(v or '').strip().lower())
        return (norm(payload.get('goal')), norm(payload.get('action')), norm(payload.get('result'))[:500],
                norm(payload.get('intent','general')), norm(payload.get('strategy','default')), norm(payload.get('domain','general')))

    @property
    def bypassed(self): return int(getattr(self._local,'bypass_depth',0))>0
    @contextmanager
    def bypass(self):
        self._local.bypass_depth=int(getattr(self._local,'bypass_depth',0))+1
        try: yield
        finally: self._local.bypass_depth=max(0,int(getattr(self._local,'bypass_depth',1))-1)
    def request(self,kind,payload,summary=''):
        if self.bypassed: return None
        def stable(value):
            if isinstance(value, dict):
                return {k:stable(v) for k,v in value.items() if k not in {"time", "timestamp", "created_at", "updated_at", "retrieved_at", "_external_validation", "episode_id", "attempt"}}
            if isinstance(value, list): return [stable(v) for v in value]
            return value
        identity = stable(payload)
        canonical=json.dumps(identity,ensure_ascii=False,sort_keys=True,default=str)
        proposal_id='learn_'+hashlib.sha256((str(kind)+'|'+canonical).encode('utf-8')).hexdigest()[:20]
        with self._lock, self._process_lock():
            existing=next((r for r in self._rows if r.get('proposal_id')==proposal_id and r.get('status') in {'pending', 'rejected'}),None)
            if existing: return dict(existing)
            approved=next((r for r in self._rows if r.get('proposal_id')==proposal_id and r.get('status')=='approved'),None)
            if approved: return dict(approved)
            duplicate_key=self._learning_duplicate_key(kind, payload)
            if duplicate_key is not None:
                duplicate=next((r for r in reversed(self._rows)
                                 if r.get('kind')==kind and r.get('status') in {'pending','approved'}
                                 and self._learning_duplicate_key(r.get('kind'), r.get('payload') or {})==duplicate_key),None)
                if duplicate:
                    return dict(duplicate)
            now=datetime.now().isoformat(timespec='seconds')
            row={'proposal_id':proposal_id,'kind':str(kind),'summary':str(summary or kind),'payload':payload,'status':'pending','created_at':now,'updated_at':now}
            self._rows.append(row); self._save(); return dict(row)
    def _save(self): atomic_write_json(self.path,self._rows)
    def pending(self,limit=50):
        with self._lock, self._process_lock():
            return [dict(r) for r in self._rows if r.get('status')=='pending'][-int(limit):][::-1]
    def history(self,limit=200):
        with self._lock, self._process_lock():
            return [dict(r) for r in self._rows[-int(limit):]][::-1]
    def get(self,proposal_id):
        with self._lock, self._process_lock():
            row=next((r for r in self._rows if r.get('proposal_id')==str(proposal_id)),None)
            return dict(row) if row else None
    def decide_many(self, proposal_ids, status='approved'):
        results=[]
        for proposal_id in list(proposal_ids or []):
            row=self.decide(proposal_id,status)
            if row is not None: results.append(row)
        return results

    def decide(self,proposal_id,status):
        status=str(status)
        if status not in {'approved','rejected'}: raise ValueError('invalid learning decision')
        with self._lock, self._process_lock():
            row=next((r for r in self._rows if r.get('proposal_id')==str(proposal_id)),None)
            if not row: return None
            if row.get('status')!='pending': return dict(row)
            row['status']=status; row['updated_at']=datetime.now().isoformat(timespec='seconds'); self._save(); return dict(row)
    def stats(self):
        with self._lock, self._process_lock():
            pending=sum(r.get('status')=='pending' for r in self._rows)
            approved=sum(r.get('status')=='approved' for r in self._rows)
            rejected=sum(r.get('status')=='rejected' for r in self._rows)
            total=len(self._rows)
            # One learning request is one XP unit; each unit is worth 1,000,000 XP.
            return {'pending':pending,'approved':approved,'rejected':rejected,'total':total,'requests':total,'xp_units':total,'xp':total*1_000_000}
