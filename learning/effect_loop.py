"""Verified effect loop: applied learning is tested against expected effects and its trust is updated.
Local, deterministic, no external models."""
from pathlib import Path
import json, hashlib
from datetime import datetime

class EffectLearningLoop:
    def __init__(self, path, learning):
        self.path=Path(path); self.learning=learning
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state={"xp":0,"validated":0,"credits":[],"evaluations":[],"retired_rules":[],"behavior_observations":[],"behavior_comparisons":[],"transfer_evaluations":[]}
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
        effect=self._effect(expected,result,verified,v)
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
    def _effect(expected,result,verified,verification=None):
        if not verified: return "unverified"
        verification = verification if isinstance(verification, dict) else {}
        if verification.get("effect_observed"):
            return "expected_effect_observed"
        e=str(expected or "").strip().lower(); r=str(result or "").strip().lower()
        if not e: return "verified_without_explicit_effect"
        if e in r: return "expected_effect_observed"
        return "verified_but_effect_text_mismatch"
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

    def observe_behavior(self, goal, result, strategy="baseline", domain="general", episode_id="", learning_applied=False):
        """Record a non-training behavioral observation for before/after comparison.
        Observation alone never grants XP and never changes learned rules.
        """
        row={"goal":str(goal),"result":str(result)[:2000],"strategy":str(strategy),
             "domain":str(domain),"episode_id":str(episode_id),
             "learning_applied":bool(learning_applied),
             "time":datetime.now().isoformat(timespec="seconds")}
        rows=self.state.setdefault("behavior_observations",[])
        # Keep one baseline per goal/domain until a learned variant is observed.
        if not learning_applied:
            existing=next((r for r in rows if r.get("goal")==row["goal"] and r.get("domain")==row["domain"] and not r.get("learning_applied")),None)
            if existing is None:
                rows.append(row)
                self._save()
            return {"mode":"baseline_recorded" if existing is None else "baseline_exists",
                    "baseline": existing or row, "mutated_learning":False}
        baseline=next((r for r in reversed(rows) if r.get("goal")==row["goal"] and r.get("domain")==row["domain"] and not r.get("learning_applied")),None)
        if baseline is None:
            rows.append(row); self._save()
            return {"mode":"awaiting_baseline","mutated_learning":False}
        changed=baseline.get("result","") != row["result"]
        comparison={"goal":row["goal"],"domain":row["domain"],"baseline_strategy":baseline.get("strategy"),
                    "new_strategy":row["strategy"],"changed":changed,
                    "baseline_result":baseline.get("result",""),"new_result":row["result"],
                    "time":row["time"]}
        self.state.setdefault("behavior_comparisons",[]).append(comparison)
        rows.append(row)
        self._save()
        return {"mode":"compared","changed":changed,"comparison":comparison,"mutated_learning":False}

    @staticmethod
    def _tokens(value):
        import re
        return {x for x in re.findall(r"[\w\u0600-\u06ff]+", str(value).lower()) if len(x)>1}

    def find_transfer_source(self, target_goal, domain="general", min_similarity=.25):
        target=self._tokens(target_goal)
        candidates=[]
        for row in self.state.get("behavior_observations",[]):
            if row.get("domain")!=str(domain) or row.get("learning_applied"): continue
            goal=str(row.get("goal",""))
            if goal==str(target_goal): continue
            tokens=self._tokens(goal)
            sim=len(target & tokens)/max(1,len(target | tokens)) if target or tokens else 0.0
            if sim>=float(min_similarity):
                candidates.append((sim,row))
        candidates.sort(key=lambda x:x[0], reverse=True)
        return candidates[0][1] if candidates else None

    def evaluate_transfer(self, source_goal, target_goal, result, expected, verification,
                          strategy="default", domain="general", episode_id="", attempt=1):
        source=self._tokens(source_goal); target=self._tokens(target_goal)
        similarity=len(source & target)/max(1,len(source | target)) if source or target else 0.0
        v=verification if isinstance(verification,dict) else {}
        score=float(v.get("score",0) or 0)
        verified=bool(v.get("verified")) and score>=.75
        row={"source_goal":str(source_goal),"target_goal":str(target_goal),
             "similarity":round(similarity,3),"result":str(result)[:1200],
             "expected":str(expected),"verified":verified,"score":score,
             "strategy":str(strategy),"domain":str(domain),"episode_id":str(episode_id),
             "attempt":int(attempt or 1),"time":datetime.now().isoformat(timespec="seconds")}
        key=hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()
        rows=self.state.setdefault("transfer_evaluations",[])
        if key not in {r.get("key") for r in rows}: rows.append({"key":key,**row})
        passed=verified and similarity>=.25
        self._save()
        return {"passed":passed,"similarity":round(similarity,3),"verified":verified,
                "score":score,"key":key,"xp_awarded":0}

    def learning_result(self, behavior_comparison, verification, transfer=None):
        changed=bool((behavior_comparison or {}).get("changed"))
        v=verification if isinstance(verification,dict) else {}
        verified=bool(v.get("verified")) and float(v.get("score",0) or 0)>=.75
        transfer_ok=bool((transfer or {}).get("passed"))
        qualified=changed and verified and transfer_ok
        return {"qualified":qualified,"behavior_changed":changed,"verified":verified,
                "transfer_passed":transfer_ok,"xp_eligible":qualified,
                "reason":"behavior_change+verification+transfer" if qualified else "evidence_chain_incomplete"}

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

    def replay_candidates(self, limit=10):
        """Prioritize replay by uncertainty, novelty, failure, then recency."""
        rows = list(self.state.get("evaluations", []))
        def priority(row):
            score = float(row.get("score", 0.0))
            uncertainty = 1.0 - abs(score - 0.5) * 2.0
            failure = 1.0 if row.get("verified") and score < .55 else 0.0
            return uncertainty * .55 + failure * .30 + (1.0 if row.get("effect") != "expected_effect_observed" else 0.0) * .15
        rows.sort(key=priority, reverse=True)
        return [{"key": r.get("key"), "goal": r.get("goal"), "strategy": r.get("strategy"),
                 "score": r.get("score", 0), "priority": round(priority(r), 3)} for r in rows[:int(limit)]]

    def compare_strategies(self, goal, domain="general"):
        """Counterfactual-style comparison from verified historical outcomes."""
        rows = [r for r in self.state.get("evaluations", [])
                if r.get("goal") == str(goal) and r.get("domain") == str(domain) and r.get("verified")]
        groups = {}
        for row in rows:
            groups.setdefault(str(row.get("strategy", "default")), []).append(float(row.get("score", 0)))
        ranked = []
        for strategy, scores in groups.items():
            mean = sum(scores) / len(scores)
            failures = sum(s < .55 for s in scores)
            ranked.append({"strategy": strategy, "mean_score": round(mean, 3),
                           "samples": len(scores), "failures": failures,
                           "confidence": round(min(.95, .35 + len(scores) * .08), 3)})
        return sorted(ranked, key=lambda x: (x["mean_score"], x["samples"]), reverse=True)

    def learning_priority(self, goal, intent="general", domain="general", uncertainty=0.0, novelty=0.0):
        """Unify active-learning need with existing verified evidence."""
        meta = self.recommend_meta_strategy(goal, intent, domain)
        active = self.active_learning_request(goal, uncertainty, novelty)
        replay = self.replay_candidates(5)
        comparisons = self.compare_strategies(goal, domain)
        if comparisons and comparisons[0]["mean_score"] >= .8 and comparisons[0]["samples"] >= 2:
            action = "reuse_best_then_verify"
        elif active["needed"]:
            action = "active_experiment"
        elif replay:
            action = "replay_uncertain_evidence"
        else:
            action = "observe_and_wait"
        return {"goal": str(goal), "action": action, "meta": meta, "active": active,
                "replay": replay, "strategy_comparison": comparisons}

    def snapshot(self):
        return self.stats()
