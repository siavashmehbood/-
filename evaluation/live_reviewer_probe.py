"""One-shot live zero-budget reviewer acceptance probe for CI."""
import json, os, shutil, tempfile
from pathlib import Path
from runtime.app import IranRuntime
REPO=Path(__file__).resolve().parents[1]
def need(v,m):
    if not v: raise AssertionError(m)
def main():
    need(os.environ.get("OPENROUTER_API_KEY","").strip(),"OPENROUTER_API_KEY missing")
    with tempfile.TemporaryDirectory(prefix="iran-live-review-") as folder:
        root=Path(folder); shutil.copy(REPO/"config.json",root/"config.json")
        local={"max_attempts":4,"max_seconds":40,"providers":{"openrouter":{
          "enabled":True,"base_url":"https://openrouter.ai/api/v1","key_env":"OPENROUTER_API_KEY",
          "model":"","timeout":10,"retries":0,"cooldown":60,"min_interval":0,
          "dynamic_free_models":True,"free_model_limit":25,"model_attempts":4,"free_models_ttl":900,
          "free_policy":{"budget":0,"confirmed":False,"models":[],"expires_at":""}}}}
        (root/"reviewers.local.json").write_text(json.dumps(local),encoding="utf-8")
        runtime=IranRuntime(root)
        try:
            runtime.internet_access.enable()
            p=runtime.learning_gate.request("knowledge.add_fact",
              {"subject":"live reviewer fixture","predicate":"status","object":"verified","source":"github_actions_live_probe"},
              "Live reviewer acceptance fixture")
            result=runtime.process_one_chatgpt_learning_review()
            need(result.get("ok"),"external reviewer failed: "+json.dumps(result))
            row=runtime.chatgpt_learning_review_status(p["proposal_id"]).get("row") or {}
            need(row.get("status")=="human_pending","candidate not human-eligible")
            need(row.get("chatgpt_decision")=="learn","controlled fixture rejected")
            need(runtime.approve_learning(p["proposal_id"], human_confirmed=True, source='test_human').get("ok"),"human-gate apply failed")
            need(runtime.knowledge.best_fact("live reviewer fixture","status") is not None,"knowledge not applied")
        finally: runtime.close()
        restarted=IranRuntime(root)
        try:
            fact=restarted.knowledge.best_fact("live reviewer fixture","status")
            need(fact and fact.get("object")=="verified","knowledge lost after restart")
            need(restarted.learning_gate.get(p["proposal_id"]).get("status")=="approved","approval lost after restart")
        finally: restarted.close()
    print("LIVE_REVIEWER_E2E_PASS")
if __name__=="__main__": main()
