from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime

class BrainVersionStore:
    """Versioned local snapshots with explicit rollback; atomic JSON persistence."""
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        try: self.rows=json.loads(self.path.read_text(encoding="utf-8"))
        except Exception: self.rows=[]
        if not isinstance(self.rows,list): self.rows=[]
    def snapshot(self,state,label=""):
        row={"version":len(self.rows)+1,"label":str(label),"state":state,"created_at":datetime.now().isoformat(timespec="seconds")}
        self.rows.append(row); self.path.write_text(json.dumps(self.rows,ensure_ascii=False,indent=2),encoding="utf-8"); return row
    def latest(self): return self.rows[-1] if self.rows else None
    def rollback(self,version):
        row=next((r for r in self.rows if r.get("version")==int(version)),None); return row["state"] if row else None
    def versions(self): return [{"version":r["version"],"label":r["label"],"created_at":r["created_at"]} for r in self.rows]
