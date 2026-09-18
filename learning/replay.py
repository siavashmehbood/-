from __future__ import annotations

class ExperienceReplay:
    """Offline replay of durable experiences; no network or model calls."""
    def __init__(self, learning): self.learning=learning
    def replay(self, limit=1000):
        rows=list(self.learning.experiences[-int(limit):])
        results=[]
        for row in rows:
            results.append({"goal":row.get("goal"),"strategy":row.get("strategy"),
                            "score":float(row.get("score",0)),
                            "lesson":row.get("lesson","")})
        return results
    def summarize(self, limit=1000):
        rows=self.replay(limit); groups={}
        for r in rows:
            groups.setdefault(r["strategy"],[]).append(r["score"])
        return [{"strategy":k,"samples":len(v),"mean_score":round(sum(v)/len(v),3)}
                for k,v in sorted(groups.items(),key=lambda x:sum(x[1])/len(x[1]),reverse=True)]
    def learn(self, limit=1000):
        self.learning.auto_maintenance()
        return self.summarize(limit)
