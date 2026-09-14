from pathlib import Path
import shutil,time,json

class ImprovementManager:
    """Controlled self-improvement: snapshot, stage, test, compare and rollback."""
    def __init__(self,root,sandbox='sandbox'):
        self.root=Path(root); self.sandbox=self.root/sandbox; self.sandbox.mkdir(parents=True,exist_ok=True)
    def stage_file(self,source,name=None):
        src=Path(source); target=self.sandbox/(name or src.name); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,target); return str(target)
    def create_snapshot(self):
        stamp=time.strftime('%Y%m%d_%H%M%S'); target=self.sandbox/('snapshot_'+stamp); target.mkdir(); excluded={'.git','__pycache__','sandbox','data','logs'}; copied=0
        for src in self.root.rglob('*'):
            if not src.is_file() or any(p in excluded for p in src.parts): continue
            dst=target/src.relative_to(self.root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); copied+=1
        return {'snapshot':str(target),'files':copied}
    def manifest(self,snapshot):
        root=Path(snapshot); return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())
    def rollback(self,snapshot,paths=None):
        root=Path(snapshot); selected=paths or self.manifest(snapshot); restored=0
        for rel in selected:
            src=root/rel; dst=self.root/rel
            if src.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); restored+=1
        return {'restored':restored,'snapshot':str(root)}
    def deployment_allowed(self,config): return bool(config.get('self_improvement',{}).get('auto_deploy',False))
    def promotion_decision(self,baseline,candidate,tests_ok):
        return {'promote':bool(tests_ok and candidate>baseline),'reason':'candidate benchmark improved' if tests_ok and candidate>baseline else 'keep current version'}
