from __future__ import annotations
import json
import os
import time
from pathlib import Path

from integrations.chatgpt_review_worker import ChatGPTReviewWorker
from persistence import load_json_with_backup
from providers.reviewer import ProviderManager
from security.internet_access import InternetAccessManager

ROOT = Path(__file__).resolve().parent
BATCH_SOURCE = "direct_user_requested_teaching_100_batch"

def batch_candidate(rows):
    for row in rows:
        payload = row.get("payload", {}) or {}
        if (row.get("source") == "learning_candidate"
                and payload.get("source") == BATCH_SOURCE
                and row.get("review_status", "not_reviewed") == "not_reviewed"
                and row.get("status", "pending") in {"pending", "WAITING_FOR_REVIEWER"}):
            return row
    return None

def remaining_count(worker):
    return sum(1 for row in worker._load_rows() if batch_candidate([row]) is not None)
def build_worker():
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    internet = InternetAccessManager(ROOT / "data" / "internet_access.json")
    reviewer_config = load_json_with_backup(
        ROOT / "reviewers.local.json", config.get("reviewers", {}))
    manager = ProviderManager(
        ROOT,
        {"reviewers": reviewer_config,
         "external_access": config.get("external_access", {})},
        internet,
    )
    worker = ChatGPTReviewWorker(ROOT)
    worker.manager = manager
    worker._candidate = batch_candidate
    return worker

def main():
    worker = build_worker()
    started = time.time()
    reviewed = rejected = attempts = 0
    max_seconds = int(os.environ.get("IRAN_REVIEW_BATCH_MAX_SECONDS", "900"))
    max_attempts = int(os.environ.get("IRAN_REVIEW_BATCH_MAX_ATTEMPTS", "160"))
    while time.time() - started < max_seconds and attempts < max_attempts:
        remaining = remaining_count(worker)
        print(json.dumps({"event":"progress","remaining":remaining,
                          "reviewed":reviewed,"rejected":rejected},
                         ensure_ascii=False), flush=True)
        if remaining <= 0:
            break
        result = worker.process_one()
        attempts += 1
        if result.get("ok") and result.get("reason") == "reviewed":
            reviewed += int(result.get("learn") is True)
            rejected += int(result.get("learn") is False)
            continue
        reason = result.get("reason")
        if reason == "no_candidate":
            break
        status = result.get("status", {}) or {}
        wait = int(status.get("cooldown_seconds", 0) or 0)
        if reason in {"cooldown","interval","rate_limited","http_429","http_403",
                      "all_free_models_cooling_down"} or result.get("state") == "WAITING_FOR_REVIEWER":
            time.sleep(max(1, min(30, wait if wait > 0 else 5)))
        else:
            time.sleep(3)
    print(json.dumps({"event":"done","remaining":remaining_count(worker),
                      "reviewed":reviewed,"rejected":rejected},
                     ensure_ascii=False), flush=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
