"""One-shot live reviewer transport probe; never impersonates human approval."""
import json, os, shutil, tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.app import IranRuntime

REPO = Path(__file__).resolve().parents[1]

def main():
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("BLOCKED_EXTERNAL: OPENROUTER_API_KEY missing")
    with tempfile.TemporaryDirectory(prefix="iran-live-review-") as folder:
        root = Path(folder)
        shutil.copy(REPO / "config.json", root / "config.json")
        runtime = IranRuntime(root)
        try:
            runtime.internet_access.enable()
            proposal = runtime.learning_gate.request("knowledge.add_fact",
                {"subject":"live reviewer fixture","predicate":"status","object":"verified",
                 "source":"github_actions_transport_probe"},
                "Transport diagnostic only; this claim has no external source and must not be learned automatically.")
            result = runtime.process_one_chatgpt_learning_review()
            if not result.get("ok"):
                raise RuntimeError("BLOCKED_EXTERNAL: " + json.dumps(result))
            row = runtime.chatgpt_learning_review_status(proposal["proposal_id"]).get("row") or {}
            if row.get("status") not in {"human_pending", "rejected"}:
                raise AssertionError("Invalid reviewer result state")
            if runtime.knowledge.best_fact("live reviewer fixture", "status") is not None:
                raise AssertionError("Transport probe unexpectedly applied knowledge")
            if runtime.learning_gate.get(proposal["proposal_id"]).get("status") == "approved":
                raise AssertionError("Probe must never approve for a human")
            print("LIVE_REVIEWER_TRANSPORT_PASS; no human approval or durable learning performed")
        finally:
            runtime.close()

if __name__ == "__main__":
    main()
