"""Verified effect loop: applied learning is tested against expected effects and its trust is updated.
Local, deterministic, no external models."""
from pathlib import Path
import json, hashlib
from datetime import datetime

class EffectLearningLoop:
    def __init__(self, path, learning):
        self.path=Path(path); self.learning=learning
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state={"xp":0,"validated":0,"credits":[],"evaluations":[],"retired_rules":[]}
        self._load()

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data,dict): self.state.update(data)
        except Exception: pass

    def _save(self):
        tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _key(row):
        raw="|".join(str(row.get(k,"")) for k in ("goal","action","result","strategy","domain","episode_id","attempt"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _rules_for(self, strategy, domain):
        return [r for r in self.learning.rules
                if r.get("strategy")==strategy and r.get("domain")==domain]

    def evaluate(self, goal, action, result, expected, verification, strategy="default", domain="general", episode_id="", attempt=0):
        v=verification if isinstance(verification,dict) else {}
        verified=bool(v.get("verified",False))
        try: score=max(0.0,min(1.0,float(v.get("score",0.0)))) if verified else 0.0
        except Exception: score=0.0
        effect=self._effect(expected,result,verified)
        row={"goal":str(goal),"action":str(action),"result":str(result)[:1200],"expected":str(expected),
             "verified":verified,"score":score,"effect":effect,"strategy":str(strategy),"domain":str(domain),
             "episode_id":str(episode_id),"attempt":int(attempt or 0),"time":datetime.now().isoformat(timespec="seconds")}
        key=self._key(row)
        existing={x.get("key") for x in self.state["evaluations"]}
        if key not in existing: self.state["evaluations"].append({"key":key,**row})
        rule_updates=self._update_rules(strategy,domain,score,verified)
        credit=False
        if verified and score>=.75 and key not in {x.get("key") for x in self.state["credits"]}:
            self.state["xp"]+=1000000; self.state["validated"]+=1
            self.state["credits"].append({"key":key,"xp":1000000,"time":row["time"]}); credit=True
        self._save()
        return {"verified":verified,"score":score,"effect":effect,"credit_awarded":credit,
                "xp_awarded":1000000 if credit else 0,"xp_total":self.state["xp"],"rule_updates":rule_updates,
                "next_test": self._next_test(strategy,domain,score)}

    @staticmethod
    def _effect(expected,result,verified):
        if not verified: return "unverified"
        e=str(expected or "").strip().lower(); r=str(result or "").strip().lower()
        if not e: return "verified_without_explicit_effect"
        return "expected_effect_observed" if e in r else "verified_but_effect_text_mismatch"
    def _update_rules(self,strategy,domain,score,verified):
        changed=[]
        for rule in self._rules_for(strategy,domain):
            old=float(rule.get("confidence",.5))
            samples=int(rule.get("validated_uses",0))
            if verified and score>=.75:
                new=min(.99,old+.04); rule["validated_uses"]=samples+1
                rule["successful_uses"]=int(rule.get("successful_uses",0))+1
            elif verified and score<.55:
                new=max(.05,old-.08); rule["failed_uses"]=int(rule.get("failed_uses",0))+1
            else: continue
            rule["confidence"]=round(new,3); rule["last_evaluated"]=datetime.now().isoformat(timespec="seconds")
            rule["status"]="retired" if new<.25 and int(rule.get("failed_uses",0))>=2 else ("trusted" if new>=.80 else "candidate")
            if rule["status"]=="retired" and rule.get("rule") not in self.state["retired_rules"]:
                self.state["retired_rules"].append(rule.get("rule",""))
            changed.append({"strategy":strategy,"old":round(old,3),"new":rule["confidence"],"status":rule["status"]})
        return changed

    def _next_test(self,strategy,domain,score):
        if score>=.75: return {"mode":"retest_transfer","strategy":strategy,"domain":domain}
        if score<.55: return {"mode":"change_strategy","avoid":strategy,"domain":domain}
        return {"mode":"gather_evidence","strategy":strategy,"domain":domain}

    def stats(self):
        return {"xp":int(self.state["xp"]),"validated":int(self.state["validated"]),
                "evaluations":len(self.state["evaluations"]),"credits":len(self.state["credits"]),
                "retired_rules":len(self.state["retired_rules"])}
    def recommend_meta_strategy(self, goal, intent="general", domain="general"):
        """Meta-learning: choose how to learn, not only what action to reuse."""
        evidence=self.learning.adapt(goal,intent,domain)
        rules=[r for r in evidence.get("learned_rules",[]) if r.get("status","candidate")!="retired"]
        if not rules:
            mode="active-evidence"
        elif any(float(r.get("confidence",0))>=.8 for r in rules):
            mode="reuse-then-verify"
        else:
            mode="compare-and-retest"
        return {"mode":mode,"strategy":evidence.get("recommended_strategy","evidence-first"),
                "evidence":evidence,"exploration_required":mode!="reuse-then-verify"}

    def active_learning_request(self, goal, uncertainty, novelty=0.0):
        """Ask for learning only when uncertainty/novelty justify its cost."""
        u=float(uncertainty or 0); n=float(novelty or 0)
        needed=u>=.55 or n>=.45
        return {"needed":needed,"goal":str(goal),"uncertainty":round(u,3),"novelty":round(n,3),
                "reason":"high uncertainty or novel capability gap" if needed else "routine interaction"}

    def snapshot(self):
        return self.stats()
