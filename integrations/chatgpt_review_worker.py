"""Single-candidate ChatGPT validation worker for the IRAN learning queue.

The worker is deliberately separate from queue/status readers.  It performs at
most one external request per invocation and persists cooldown state so GUI
refreshes and process restarts cannot bypass rate limiting.
"""
from __future__ import annotations

import json
from contextlib import nullcontext
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

    @classmethod
    def _valid_state(cls, value):
        if not isinstance(value, dict):
            return False
        backoff = value.get("backoff_seconds", 15)
        if isinstance(backoff, bool) or not isinstance(backoff, int) or backoff < 0:
            return False
        for key in ("next_allowed_at", "last_request_at", "last_success_at"):
            timestamp = value.get(key)
            if timestamp is not None and cls._parse_iso(timestamp) is None:
                return False
        return value.get("last_error") is None or isinstance(value.get("last_error"), str)

    def _load_state(self):
        default = {
            "next_allowed_at": None,
            "backoff_seconds": 15,
            "last_request_at": None,
            "last_success_at": None,
            "last_error": None,
        }
        value = load_critical_json(self.state_path, {}, validator=self._valid_state)
        default.update({key: value[key] for key in default if key in value})
        return default

    def _save_state(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.state_path, state)

    def status(self):
        has_state = self.state_path.exists() or self.state_path.with_suffix(self.state_path.suffix + ".bak").exists()
        try:
            state = self._load_state()
        except StateCorruptionError:
            return {"state":"ERROR", "last_error":"worker_state_corrupt",
                    "next_allowed_at":None, "cooldown":True, "cooldown_seconds":0}
        now = self.clock()
        next_allowed = self._parse_iso(state.get("next_allowed_at"))
        return {
            "state": "READY" if has_state else "UNINITIALIZED",
            "next_allowed_at": state.get("next_allowed_at"),
            "backoff_seconds": int(state.get("backoff_seconds") or 15),
            "last_request_at": state.get("last_request_at"),
            "last_success_at": state.get("last_success_at"),
            "last_error": state.get("last_error"),
            "cooldown": bool(next_allowed and next_allowed > now),
            "cooldown_seconds": max(0, int(next_allowed - now)) if next_allowed and next_allowed > now else 0,
        }

    def _candidate(self, rows, proposal_id=None):
        # Review durable knowledge/evidence before low-value planning requests.
        # Within the same class keep FIFO order to avoid starvation.
        priorities = {
            "knowledge.contradict": 100, "trusted_knowledge.bootstrap": 95,
            "knowledge.add_fact": 90, "memory.add_semantic_fact": 85,
            "outcome.record": 80, "procedural.upsert": 75,
            "procedural.record_outcome": 74, "skills.upsert": 73,
            "skills.promote_composition": 72, "skills.execution_outcome": 71,
            "memory.add_lesson": 70, "learning.record_experience": 60,
            "user_model.record_facts": 50, "learning.goal_request": 10,
        }
        candidates = [
            (index, row) for index, row in enumerate(rows)
            if row.get("source") in {"learning_gate", "learning_candidate"}
            and (proposal_id is None
                 or str(row.get("proposal_id")) == str(proposal_id))
            and row.get("review_status", "not_reviewed") == "not_reviewed"
            and row.get("status", "pending") in {"pending", "WAITING_FOR_REVIEWER"}
        ]
        if not candidates:
            return None
        if proposal_id is not None:
            return candidates[0][1]
        _, row = max(
            candidates,
            key=lambda item: (priorities.get(item[1].get("kind"), 40), -item[0]),
        )
        return row

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

    def process_one(self, proposal_id=None):
        """Validate one candidate, optionally targeting one durable proposal ID."""
        with self._lock, file_lock(self.root / "data" / "review_worker.lock"):
            now = self.clock()
            if self.manager is not None and not self.manager.internet.status()["enabled"]:
                candidate = self._candidate(self._load_rows(), proposal_id)
                return self._waiting((candidate or {}).get("proposal_id"), "internet_off")
            try:
                state = self._load_state()
            except StateCorruptionError:
                candidate = self._candidate(self._load_rows(), proposal_id)
                return self._waiting((candidate or {}).get("proposal_id"), "worker_state_corrupt")
            next_allowed = self._parse_iso(state.get("next_allowed_at"))
            if next_allowed and next_allowed > now:
                return {"ok": False, "reason": "cooldown", "status": self.status()}
            rows = self._load_rows()
            row = self._candidate(rows, proposal_id)
            if row is None:
                return {"ok": True, "reason": "no_candidate",
                        "proposal_id": proposal_id, "status": self.status()}
            last_request = self._parse_iso(state.get("last_request_at"))
            if last_request and now - last_request < self.MIN_INTERVAL:
                wait_until = last_request + self.MIN_INTERVAL
                state["next_allowed_at"] = self._iso(wait_until)
                self._save_state(state)
                return {"ok": False, "reason": "interval", "status": self.status()}
            state["last_request_at"] = self._iso(now)
            state["last_error"] = None
            self._save_state(state)
            permission = self.manager.internet.status() if self.manager is not None else None
            try:
                result = (self.transport or self._default_transport)(dict(row))
                if not isinstance(result, dict) or not isinstance(result.get("learn"), bool):
                    raise ValueError("validator returned invalid decision")
                # Injected transports and managed providers share one payload
                # contract; invalid confidence/corrections never become approval.
                from providers.reviewer import decision
                result = {**result, **decision(result)}
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
            # Commit under the original permission generation; off/on cannot
            # revive a response authorized by an earlier permission.
            guard = (self.manager.internet.commit_permission(permission["generation"])
                     if permission is not None else nullcontext())
            try:
                with guard:
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
                    # Only externally accepted candidates are eligible for human review.
                    # Reviewer rejection ends the candidate before the human queue.
                    row["status"] = "human_pending" if result["learn"] else "rejected"
                    row["reviewed_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
                    with json_transaction(self.reviews_path, []) as current:
                        target = next((r for r in current if r.get("proposal_id") == row.get("proposal_id")), None)
                        # Do not resurrect a deleted/rejected candidate after an in-flight request.
                        if target is None or target.get("status") not in {"pending", "WAITING_FOR_REVIEWER"}:
                            return {"ok": False, "reason": "candidate_changed"}
                        target.pop("failure_reason", None)
                        target.update(row)
                        target.pop("failure_reason", None)
                    state["next_allowed_at"] = self._iso(now + self.MIN_INTERVAL)
                    state["backoff_seconds"] = 15
                    state["last_success_at"] = self._iso(now)
                    state["last_error"] = None
                    self._save_state(state)
                    return {"ok": True, "reason": "reviewed", "proposal_id": row.get("proposal_id"), "learn": result["learn"], "status": self.status()}

            except PermissionError as exc:
                reason = str(exc)
                state["next_allowed_at"] = self._iso(self.clock() + self.MIN_INTERVAL)
                state["last_error"] = reason
                self._save_state(state)
                return self._waiting(row.get("proposal_id"), reason)


__all__ = ["ChatGPTReviewWorker", "RateLimitError"]
