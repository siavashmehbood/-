from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

class ErrorMemory:
    """Persistent local memory of verified failures and recovery context."""
    def __init__(self, path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        try: self.rows=json.loads(self.path.read_text(encoding="utf-8"))
        except Exception: self.rows=[]
        if not isinstance(self.rows,list): self.rows=[]
    def record(self, goal, strategy, error, cause="", recovery="", verified=False):
        key=(str(goal).strip(),str(strategy).strip(),str(error).strip()[:500])
        if any((r.get("goal"),r.get("strategy"),r.get("error"))==key for r in self.rows): return False
        self.rows.append({"goal":str(goal),"strategy":str(strategy),"error":str(error)[:2000],
                          "cause":str(cause),"recovery":str(recovery),"verified":bool(verified),
                          "created_at":datetime.now().isoformat(timespec="seconds")})
        self.rows=self.rows[-5000:]; self.path.write_text(json.dumps(self.rows,ensure_ascii=False,indent=2),encoding="utf-8"); return True
    def search(self, goal, limit=8):
        q=str(goal).lower()
        rows=[r for r in self.rows if q in r.get("goal","").lower() or q in r.get("error","").lower()]
        return rows[-limit:][::-1]
    def stats(self): return {"errors":len(self.rows),"verified_recoveries":sum(bool(r.get("verified")) for r in self.rows)}
