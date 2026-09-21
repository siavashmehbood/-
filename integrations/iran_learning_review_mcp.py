import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security.learning_gate import LearningGate
from persistence import file_lock, atomic_write_json, load_json_with_backup

REVIEWS = ROOT / "data" / "chatgpt_reviews.json"


def load_rows():
    try:
        rows = json.loads(REVIEWS.read_text(encoding="utf-8")) if REVIEWS.exists() else []
    except Exception:
        rows = []
    return rows if isinstance(rows, list) else []


def save_rows(rows):
    REVIEWS.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(REVIEWS, rows)


def reply(i, result):
    return {"jsonrpc": "2.0", "id": i, "result": result}


def err(i, code, message):
    return {"jsonrpc": "2.0", "id": i, "error": {"code": code, "message": message}}
def _review_payload(row):
    return {
        "proposal_id": str(row.get("proposal_id", "")),
        "kind": row.get("kind"), "payload": row.get("payload", {}),
        "question": str(row.get("question", "")),
        "goal": str(row.get("goal", "")),
        "action": str(row.get("action", "")),
        "answer": str(row.get("answer", "")),
        "lesson": str(row.get("lesson", "")),
        "domain": str((row.get("payload") or {}).get("domain", "")),
    }


def _handle(req):
    i = req.get("id")
    method = req.get("method", "")

    if method == "initialize":
        return reply(i, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "iran-learning-review", "version": "2.0.0"},
        })

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return reply(i, {"tools": [
            {
                "name": "learning_review_pending",
                "description": "Get the next IRAN learning candidate for ChatGPT factual review. A candidate must be classified correct or incorrect before it can reach the human approval queue.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
                },
            },
            {
                "name": "learning_review_decide",
                "description": "Record ChatGPT's factual review. learn=false rejects the candidate and advances the queue. learn=true sends it to the human approval queue. This never applies durable learning.",
                "inputSchema": {
                    "type": "object",
                    "required": ["proposal_id", "learn", "reason"],
                    "properties": {
                        "proposal_id": {"type": "string"},
                        "learn": {"type": "boolean"},
                        "reason": {"type": "string"},
                        "corrections": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        ]})


    if method != "tools/call":
        return err(i, -32601, "method_not_found")

    params = req.get("params") or {}
    name = params.get("name", "")
    args = params.get("arguments") or {}
    rows = load_rows()

    if name == "learning_review_pending":
        limit = min(20, max(1, int(args.get("limit", 1))))
        pending = [
            r for r in rows
            if r.get("source") == "learning_gate"
            and r.get("review_status", "not_reviewed") == "not_reviewed"
            and r.get("status", "pending") in {"pending", "WAITING_FOR_REVIEWER"}
        ]
        data = [_review_payload(r) for r in pending[:limit]]
        return reply(i, {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]})

    if name == "learning_review_decide":
        pid = str(args.get("proposal_id", "")).strip()
        learn = args.get("learn")
        reason = str(args.get("reason", "")).strip()
        corrections = args.get("corrections", [])
        if not pid or not isinstance(learn, bool) or not reason:
            return err(i, -32602, "proposal_id, learn and reason are required")

        row = next((r for r in rows if str(r.get("proposal_id", "")) == pid), None)
        if row is None:
            return err(i, -32004, "proposal_not_found")

        if row.get("review_status") == "reviewed":
            return reply(i, {"content": [{"type": "text", "text": json.dumps({
                "ok": True,
                "proposal_id": pid,
                "learn": row.get("chatgpt_decision") == "learn",
                "next_step": "human_approval_required" if row.get("chatgpt_decision") == "learn" else "rejected",
                "already_reviewed": True,
            }, ensure_ascii=False)}]})

        if row.get("status") not in {"pending", "WAITING_FOR_REVIEWER"}:
            return err(i, -32006, "candidate_not_pending")
        if corrections: learn = False
        row["provider"] = "external_mcp_reviewer"
        row["review"] = json.dumps({
            "learn": learn,
            "reason": reason,
            "corrections": corrections if isinstance(corrections, list) else [],
        }, ensure_ascii=False)
        row["review_status"] = "reviewed"
        row["chatgpt_decision"] = "learn" if learn else "reject"
        row["reviewed_at"] = datetime.now().isoformat(timespec="seconds")

        gate = LearningGate(ROOT / "data/learning_proposals.json")
        if learn:
            row["status"] = "human_pending"
            next_step = "human_approval_required"
        else:
            rejected = gate.decide(pid, "rejected")
            if rejected is None:
                return err(i, -32005, "proposal_rejection_failed")
            row["status"] = "rejected"
            next_step = "next_candidate"

        save_rows(rows)
        return reply(i, {"content": [{"type": "text", "text": json.dumps({
            "ok": True,
            "proposal_id": pid,
            "learn": learn,
            "reason": reason,
            "next_step": next_step,
        }, ensure_ascii=False)}]})

    return err(i, -32601, "tool_not_found")


def handle(req):
    with file_lock(REVIEWS.with_suffix(REVIEWS.suffix + ".lock")):
        return _handle(req)


if __name__ == "__main__":
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            out = handle(json.loads(line))
            if out is not None:
                sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + chr(10))
                sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(json.dumps(err(None, -32603, type(exc).__name__), ensure_ascii=False) + chr(10))
            sys.stdout.flush()
