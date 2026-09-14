import re
from collections import Counter

class SemanticMemory:
    """Three-layer local memory with concept extraction and experience consolidation."""
    STOP={'این','آن','اون','همین','همون','برای','درباره','است','هست','یک','من','تو','ما','را','رو','به','از','در','که','و','با','می','شود','شد'}
    def __init__(self,store): self.store=store
    def tokens(self,text):
        words=re.findall(r'[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]{2,}',str(text).lower())
        return {w for w in words if w not in self.STOP}
    def concepts(self,text,limit=10):
        counts=Counter(self.tokens(text)); return [x for x,_ in counts.most_common(limit)]
    def add_fact(self,subject,predicate,value,confidence=.65,source='inference'):
        return self.store.add_semantic_fact(subject,predicate,value,confidence,source)
    def add_lesson(self,goal,lesson,confidence=.6,source='experience'):
        return self.store.add_lesson(goal,lesson,confidence,source)
    def recall(self,query,limit=8): return self.store.semantic_search(query,limit)
    def lessons(self,goal,limit=8): return self.store.lesson_search(goal,limit)
    def consolidate(self,limit=20):
        rows=self.store.recent(limit*2); facts=0; seen=set()
        for kind,content,_ in rows:
            if kind not in {'user','assistant','event','tool_result'}: continue
            cs=self.concepts(content,4)
            if len(cs)<2: continue
            key=(cs[0],cs[1])
            if key in seen: continue
            seen.add(key); self.add_fact(cs[0],'related_to',cs[1],.42,'episodic-consolidation'); facts+=1
        return {'processed':len(rows),'facts_added':facts,'unique_relations':len(seen)}
    def consolidate_experience(self,goal,score,strategy):
        if float(score)>=.8: lesson=f'استراتژی موفق «{strategy}» را در شرایط مشابه دوباره استفاده کن و سپس نتیجه را بررسی کن.'; conf=.78
        elif float(score)>=.55: lesson=f'استراتژی «{strategy}» قابل استفاده است اما قبل از تکرار شواهد بیشتری لازم است.'; conf=.58
        else: lesson=f'استراتژی «{strategy}» در این تجربه ضعیف بود؛ ابتدا علت را جدا کن و مسیر جایگزین آزمایش کن.'; conf=.72
        return self.add_lesson(goal,lesson,conf,'post-action-learning')
    def decay(self,days=120): return self.store.decay(days)
    def profile(self,query=''):
        return {'facts':self.store.semantic_stats(),'matches':self.recall(query,6) if query else [],'lessons':self.lessons(query,4) if query else []}
