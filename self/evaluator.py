import py_compile
from pathlib import Path
from time import perf_counter
import re

class Evaluator:
    """Multi-signal evaluator for code, response quality, evidence and regression safety."""
    def __init__(self,root): self.root=Path(root)

    def compile_all(self):
        failures=[]; checked=0
        for path in self.root.rglob('*.py'):
            if '__pycache__' in path.parts or 'sandbox' in path.parts: continue
            checked+=1
            try: py_compile.compile(str(path),doraise=True)
            except Exception as exc: failures.append({'file':str(path.relative_to(self.root)),'error':str(exc)})
        return {'ok':not failures,'checked':checked,'failures':failures}

    def smoke_test(self):
        started=perf_counter(); result=self.compile_all(); result.update({'test':'python-compile','elapsed_ms':round((perf_counter()-started)*1000,2)}); return result

    def score(self,goal,answer):
        if not answer:return 0.0
        text=str(answer).strip().lower(); g=str(goal).strip().lower(); score=.30
        if len(text)>20: score+=.15
        if len(text)>80: score+=.05
        if any(k in text for k in ('درک','بررسی','نتیجه','هدف','اقدام','شواهد')): score+=.15
        goal_words=[w for w in re.findall(r'[\wآ-ی]+',g) if len(w)>2]
        if goal_words and any(w in text for w in goal_words): score+=.15
        if any(x in text for x in ('error','failed','ناموفق','نمی‌دانم')): score-=.20
        return round(max(0,min(1,score)),3)

    def evaluate_answer(self, goal, answer, evidence=None, unknown=False):
        goal_text=str(goal).strip().lower(); answer_text=str(answer).strip().lower(); evidence=list(evidence or [])
        goal_words={w for w in re.findall(r'[\wآ-ی]+',goal_text) if len(w)>2}
        overlap=sum(1 for w in goal_words if w in answer_text)
        relevance=min(1.0, overlap/max(1,len(goal_words)))
        directness=1.0 if answer_text and not answer_text.startswith(('intent =','hypotheses =')) else .1
        clarity=1.0 if answer_text and len(answer_text) <= 900 else .6
        grounding=1.0 if evidence and any(str(item).strip() for item in evidence) else (.7 if unknown else .35)
        calibration=.9 if unknown and ('unknown' in answer_text or 'نمی‌دانم' in answer_text) else .65
        values={k:round(v,3) for k,v in {'relevance':relevance,'directness':directness,'grounding':grounding,'clarity':clarity,'uncertainty_calibration':calibration}.items()}
        values['overall']=round(sum(values.values())/len(values),3)
        return values

    def evidence_score(self,answer,context):
        if not context:return .25
        text=str(answer).lower(); hits=sum(1 for row in context if len(row)>1 and any(w in text for w in str(row[1]).lower().split() if len(w)>3))
        return round(min(1,.25+.15*hits),3)

    def evaluate_candidate(self,candidate_root):
        result=Evaluator(candidate_root).smoke_test(); result['candidate']=str(candidate_root); return result

    def compare(self,baseline,candidate):
        code_gain=(1 if candidate.get('ok') else 0)-(1 if baseline.get('ok') else 0)
        fewer=len(candidate.get('failures',[]))<len(baseline.get('failures',[]))
        return {'better':code_gain>0 or (code_gain==0 and fewer),'code_gain':code_gain,'baseline':baseline,'candidate':candidate}
