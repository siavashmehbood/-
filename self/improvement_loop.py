from dataclasses import dataclass,field
from pathlib import Path
import json,time,hashlib,shutil

@dataclass
class ImprovementCandidate:
    target:str; hypothesis:str; baseline:float; candidate:float=0.0; status:str='proposed'; evidence:list[str]=field(default_factory=list)

class SelfImprovementLoop:
    """Closed-loop local improvement: diagnose weakness, snapshot, test, compare and retain/rollback."""
    def __init__(self,root):
        self.root=Path(root);self.dir=self.root/'sandbox'/'improvement';self.dir.mkdir(parents=True,exist_ok=True)
        self.registry=self.root/'data'/'improvements.jsonl';self.registry.parent.mkdir(parents=True,exist_ok=True)
    def propose(self,target,weakness,baseline):
        return ImprovementCandidate(str(target),f'Improve {target}: {weakness}',float(baseline))
    def compare(self,candidate,score,required_gain=.01):
        candidate.candidate=float(score);candidate.status='accepted' if score>=candidate.baseline+required_gain else 'rejected'
        with self.registry.open('a',encoding='utf-8') as f:f.write(json.dumps({**candidate.__dict__,'ts':time.time()},ensure_ascii=False)+'\n')
        return candidate
    def snapshot(self,paths):
        stamp=time.strftime('%Y%m%d_%H%M%S');out=self.dir/stamp;out.mkdir(parents=True,exist_ok=True)
        manifest=[]
        for path in paths:
            p=Path(path)
            if p.exists() and p.is_file():
                dst=out/p.name;shutil.copy2(p,dst);manifest.append({'source':str(p),'name':p.name,'sha256':self._hash(p)})
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');return out
    def _hash(self,path):
        h=hashlib.sha256()
        with Path(path).open('rb') as f:
            for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
        return h.hexdigest()
    def rollback(self,snapshot,targets):
        restored=[];snap=Path(snapshot)
        for target in targets:
            src=snap/Path(target).name;dst=Path(target)
            if src.exists():shutil.copy2(src,dst);restored.append(str(dst))
        return restored
    def diagnose(self,benchmark):
        scores=benchmark.get('scores',{}) if isinstance(benchmark,dict) else {}
        weak=sorted(scores.items(),key=lambda x:x[1])
        return [{'target':k,'score':v,'priority':round(1-v,3)} for k,v in weak]
    def improvement_plan(self,benchmark):
        rows=self.diagnose(benchmark)
        return {'target':rows[0]['target'] if rows else 'language','baseline':rows[0]['score'] if rows else 0.,
                'steps':['capture baseline','identify failure cases','change one capability','run full regression','run benchmark','compare and retain or rollback']}
    def status(self):
        rows=[]
        if self.registry.exists():
            for line in self.registry.read_text(encoding='utf-8').splitlines()[-200:]:
                try:rows.append(json.loads(line))
                except Exception:pass
        return {'candidates':len(rows),'accepted':sum(r.get('status')=='accepted' for r in rows),'rejected':sum(r.get('status')=='rejected' for r in rows),'auto_deploy':False}
