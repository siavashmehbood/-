import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\GREEN-LEAF\iran-work")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from security.learning_gate import LearningGate
REVIEWS = ROOT / "data" / "chatgpt_reviews.json"

def load_rows():
    try:
        rows = json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else []
    except Exception:
        rows = []
    return rows if isinstance(rows, list) else []

def save_rows(rows):
    REVIEWS.parent.mkdir(parents=True, exist_ok=True)
    REVIEWS.write_text(json.dumps(rows[-5000:], ensure_ascii=False, indent=2), encoding="utf-8")

def reply(i, result):
    return {"jsonrpc":"2.0","id":i,"result":result}

def err(i, code, message):
    return {"jsonrpc":"2.0","id":i,"error":{"code":code,"message":message}}

def handle(req):
    i = req.get("id")
    method = req.get("method","")
    if method == "initialize":
        return reply(i, {
            "protocolVersion":"2025-06-18",
            "capabilities":{"tools":{"listChanged":False}},
            "serverInfo":{"name":"iran-learning-review","version":"1.0.0"}
        })
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return reply(i, {"tools":[
            {
                "name":"learning_review_pending",
                "description":"Get IRAN learning candidates that ChatGPT must judge. Do not approve learning here; only review the candidates.",
                "inputSchema":{"type":"object","properties":{"limit":{"type":"integer","minimum":1,"maximum":20}}}
            },
            {
                "name":"learning_review_decide",
                "description":"Record ChatGPT's decision for one IRAN learning candidate. learn=true means worth learning; learn=false means reject. This does not apply the learning.",
                "inputSchema":{"type":"object","required":["proposal_id","learn","reason"],"properties":{
                    "proposal_id":{"type":"string"},
                    "learn":{"type":"boolean"},
                    "reason":{"type":"string"},
                    "corrections":{"type":"array","items":{"type":"string"}}
                }}
            }
        ]})
    if method != "tools/call":
        return err(i,-32601,"method_not_found")
    params = req.get("params") or {}
    name = params.get("name","")
    args = params.get("arguments") or {}
    rows = load_rows()

    if name == "learning_review_pending":
        limit = min(20,max(1,int(args.get("limit",10))))
        pending = [r for r in rows if r.get("source") == "learning_gate" and r.get("review_status","not_reviewed") != "reviewed"]
        data = [{
            "proposal_id":str(r.get("proposal_id","")),
            "goal":str(r.get("goal","")),
            "question":str(r.get("question","")),
            "action":str(r.get("action","")),
            "answer":str(r.get("answer","")),
            "lesson":str(r.get("lesson","")),
            "domain":str((r.get("payload") or {}).get("domain",""))
        } for r in pending[:limit]]
        return reply(i,{"content":[{"type":"text","text":json.dumps(data,ensure_ascii=False)}]})

    if name == "learning_review_decide":
        pid = str(args.get("proposal_id","")).strip()
        learn = args.get("learn")
        reason = str(args.get("reason","")).strip()
        if not pid or not isinstance(learn,bool) or not reason:
            return err(i,-32602,"proposal_id, learn and reason are required")
        for row in rows:
            if str(row.get("proposal_id","")) == pid:
                row["review"] = json.dumps({
                    "learn":learn,"reason":reason,
                    "corrections":args.get("corrections",[])
                },ensure_ascii=False)
                row["review_status"] = "reviewed"
                row["chatgpt_decision"] = "learn" if learn else "reject"
                row["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
                save_rows(rows)
                if not learn:
                    gate = LearningGate(ROOT / "data/learning_proposals.json")
                    rejected = gate.decide(pid, "rejected")
                    if rejected is None:
                        return err(i,-32005,"proposal_rejection_failed")
                return reply(i,{"content":[{"type":"text","text":json.dumps({
                    "ok":True,"proposal_id":pid,"learn":learn,"reason":reason,
                    "next_step":"human_approval_required" if learn else "rejected"
                },ensure_ascii=False)}]})
        return err(i,-32004,"proposal_not_found")

    return err(i,-32601,"tool_not_found")

for line in sys.stdin:
    line=line.strip()
    if not line:
        continue
    try:
        out=handle(json.loads(line))
        if out is not None:
            sys.stdout.write(json.dumps(out,ensure_ascii=False,separators=(",",":"))+"\n")
            sys.stdout.flush()
    except Exception as exc:
        sys.stdout.write(json.dumps(err(None,-32603,type(exc).__name__),ensure_ascii=False)+"\n")
        sys.stdout.flush()
