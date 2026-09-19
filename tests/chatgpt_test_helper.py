import json
from persistence import atomic_write_json

def mark_chatgpt_correct(runtime, proposal_id, reason):
    runtime.sync_chatgpt_learning_reviews()
    path = runtime._chatgpt_review_path()
    rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    for row in rows:
        if str(row.get("proposal_id")) == str(proposal_id):
            row["review"] = json.dumps({"learn": True, "reason": reason, "corrections": []}, ensure_ascii=False)
            row["review_status"] = "reviewed"
            row["chatgpt_decision"] = "learn"
            row["status"] = "human_pending"
            atomic_write_json(path, rows[-5000:])
            return
    raise AssertionError("proposal missing from ChatGPT review queue")
