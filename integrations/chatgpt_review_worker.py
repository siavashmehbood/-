"""Single-candidate ChatGPT validation worker for the IRAN learning queue.

The worker is deliberately separate from queue/status readers.  It performs at
most one external request per invocation and persists cooldown state so GUI
refreshes and process restarts cannot bypass rate limiting.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, json_transaction, load_critical_json, StateCorruptionError, file_lock


class ReviewerUnavailable(Exception):
    pass


class RateLimitError(Exception):
    def __init__(self, retry_after=None, message="rate limited"):
        super().__init__(message)
        self.retry_after = retry_after


class ChatGPTReviewWorker:
    MIN_INTERVAL = 15
    BACKOFFS = (15, 30, 60, 120, 300)

    def __init__(self, root, transport=None, clock=None):
        self.root = Path(root)
        self.reviews_path = self.root / "data" / "chatgpt_reviews.json"
        self.state_path = self.root / "data" / "chatgpt_review_state.json"
        self.transport = transport
        self.clock = clock or time.time
        self._lock = threading.Lock()
        self.manager = None

    @staticmethod
    def _iso(ts):
        return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None

    @staticmethod
    def _parse_iso(value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    def _load_rows(self):
        rows = load_critical_json(self.reviews_path, [])
        return rows if isinstance(rows, list) else []

    def _save_rows(self, rows):
        self.reviews_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.reviews_path, rows)

    def _load_state(self):
        default = {
            "next_allowed_at": None,
            "backoff_seconds": 15,
            "last_request_at": None,
            "last_success_at": None,
            "last_error": None,
        }
        value = load_critical_json(self.state_path, {})
        default.update({key: value[key] for key in default if key in value})
        return default

    def _save_state(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.state_path, state)

    def status(self):
        try:
            state = self._load_state()
        except StateCorruptionError:
            return {"state":"ERROR", "last_error":"worker_state_corrupt",
                    "next_allowed_at":None, "cooldown":True, "cooldown_seconds":0}
        now = self.clock()
        next_allowed = self._parse_iso(state.get("next_allowed_at"))
        return {
            "next_allowed_at": state.get("next_allowed_at"),
            "backoff_seconds": int(state.get("backoff_seconds") or 15),
            "last_request_at": state.get("last_request_at"),
            "last_success_at": state.get("last_success_at"),
            "last_error": state.get("last_error"),
            "cooldown": bool(next_allowed and next_allowed > now),
            "cooldown_seconds": max(0, int(next_allowed - now)) if next_allowed and next_allowed > now else 0,
        }

    def _candidate(self, rows):
        return next((row for row in rows if row.get("source") == "learning_gate"
                      and row.get("review_status", "not_reviewed") == "not_reviewed"
                      and row.get("status", "pending") in {"pending", "WAITING_FOR_REVIEWER"}), None)

    def _windows_user_env(self, name):
        if os.name != "nt":
            return ""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                return str(winreg.QueryValueEx(key, name)[0]).strip()
        except Exception:
            return ""

    def _env_value(self, name, default=""):
        return (os.environ.get(name) or self._windows_user_env(name) or default).strip()

    def _default_transport(self, row):
        if self.manager is None:
            raise ReviewerUnavailable("reviewer_manager_not_configured")
        reviewed = self.manager.review(row)
        if not reviewed.get("ok"):
            raise ReviewerUnavailable(reviewed.get("reason", "no_reviewer_available"))
        return reviewed["result"]

    def _waiting(self, proposal_id, reason):
        with json_transaction(self.reviews_path, []) as rows:
            for row in rows:
                if row.get("proposal_id") == proposal_id and row.get("status") in {"pending", "WAITING_FOR_REVIEWER"}:
                    row["status"] = "WAITING_FOR_REVIEWER"
                    row["failure_reason"] = reason
        return {"ok":False, "reason":reason, "state":"WAITING_FOR_REVIEWER", "status":self.status()}

    def process_one(self):
        """Validate one candidate, or return a durable cooldown/no-candidate result."""
        with self._lock, file_lock(self.root / "data" / "review_worker.lock"):
            now = self.clock()
            if self.manager is not None and not self.manager.internet.status()["enabled"]:
                candidate = self._candidate(self._load_rows())
                return self._waiting((candidate or {}).get("proposal_id"), "internet_off")
            try:
                state = self._load_state()
            except StateCorruptionError:
                candidate = self._candidate(self._load_rows())
                return self._waiting((candidate or {}).get("proposal_id"), "worker_state_corrupt")
            next_allowed = self._parse_iso(state.get("next_allowed_at"))
            if next_allowed and next_allowed > now:
                return {"ok": False, "reason": "cooldown", "status": self.status()}
            rows = self._load_rows()
            row = self._candidate(rows)
            if row is None:
                return {"ok": True, "reason": "no_candidate", "status": self.status()}
            last_request = self._parse_iso(state.get("last_request_at"))
            if last_request and now - last_request < self.MIN_INTERVAL:
                wait_until = last_request + self.MIN_INTERVAL
                state["next_allowed_at"] = self._iso(wait_until)
                self._save_state(state)
                return {"ok": False, "reason": "interval", "status": self.status()}
            state["last_request_at"] = self._iso(now)
            state["last_error"] = None
            self._save_state(state)
            try:
                result = (self.transport or self._default_transport)(dict(row))
                if not isinstance(result, dict) or not isinstance(result.get("learn"), bool):
                    raise ValueError("validator returned invalid decision")
            except ReviewerUnavailable as exc:
                state["next_allowed_at"] = self._iso(now + self.MIN_INTERVAL)
                state["last_error"] = str(exc)
                self._save_state(state)
                return self._waiting(row.get("proposal_id"), str(exc))
            except RateLimitError as exc:
                previous = int(state.get("backoff_seconds") or 15)
                retry = max(0, float(exc.retry_after)) if exc.retry_after is not None else previous
                retry = min(300, max(15, int(retry)))
                state["backoff_seconds"] = min(300, previous * 2) if exc.retry_after is None else retry
                state["next_allowed_at"] = self._iso(now + retry)
                state["last_error"] = "HTTP 429"
                self._save_state(state)
                return {"ok": False, "reason": "rate_limited", "proposal_id": row.get("proposal_id"), "status": self.status()}
            except Exception as exc:
                state["next_allowed_at"] = self._iso(now + int(state.get("backoff_seconds") or 15))
                state["last_error"] = f"{type(exc).__name__}: {exc}"[:500]
                self._save_state(state)
                return {"ok": False, "reason": "worker_error", "error": state["last_error"], "status": self.status()}
            row["provider"] = result.get("provider", "injected_transport")
            row["model"] = result.get("model", "")
            row.pop("failure_reason", None)
            row["review"] = json.dumps({
                "learn": result["learn"],
                "reason": str(result.get("reason", "")),
                "corrections": result.get("corrections", []) if isinstance(result.get("corrections", []), list) else [],
                "confidence": result.get("confidence"),
                "answer": result.get("answer", ""),
            }, ensure_ascii=False)
            row["review_status"] = "reviewed"
            row["chatgpt_decision"] = "learn" if result["learn"] else "reject"
            row["status"] = "human_pending" if result["learn"] else "rejected"
            row["reviewed_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
            with json_transaction(self.reviews_path, []) as current:
                target = next((r for r in current if r.get("proposal_id") == row.get("proposal_id")), None)
                # Do not resurrect a deleted/rejected candidate after an in-flight request.
                if target is None or target.get("status") not in {"pending", "WAITING_FOR_REVIEWER"}:
                    return {"ok": False, "reason": "candidate_changed"}
                target.update(row)
            state["next_allowed_at"] = self._iso(now + self.MIN_INTERVAL)
            state["backoff_seconds"] = 15
            state["last_success_at"] = self._iso(now)
            state["last_error"] = None
            self._save_state(state)
            return {"ok": True, "reason": "reviewed", "proposal_id": row.get("proposal_id"), "learn": result["learn"], "status": self.status()}


__all__ = ["ChatGPTReviewWorker", "RateLimitError"]
