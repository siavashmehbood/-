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

from persistence import atomic_write_json


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
        try:
            rows = json.loads(self.reviews_path.read_text(encoding="utf-8")) if self.reviews_path.exists() else []
        except (OSError, ValueError):
            rows = []
        return rows if isinstance(rows, list) else []

    def _save_rows(self, rows):
        self.reviews_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.reviews_path, rows[-5000:])

    def _load_state(self):
        default = {
            "next_allowed_at": None,
            "backoff_seconds": 15,
            "last_request_at": None,
            "last_success_at": None,
            "last_error": None,
        }
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}
        except (OSError, ValueError):
            value = {}
        if not isinstance(value, dict):
            value = {}
        default.update({key: value[key] for key in default if key in value})
        return default

    def _save_state(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.state_path, state)

    def status(self):
        state = self._load_state()
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
                      and row.get("status", "pending") == "pending"), None)

    def _default_transport(self, row):
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")
        default_model = "gpt-5-mini" if "manus.im" in base else "gpt-4o-mini"
        model = os.environ.get("OPENAI_MODEL", default_model)
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Validate one learning candidate. Return JSON only with learn (boolean), reason (string), corrections (array), confidence (number), and answer (string). Do not apply learning."},
                {"role": "user", "content": json.dumps({"candidate": row}, ensure_ascii=False)},
            ],
        }
        request = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            retry = exc.headers.get("Retry-After") if exc.headers else None
            if exc.code == 429:
                try:
                    retry = float(retry)
                except (TypeError, ValueError):
                    retry = None
                raise RateLimitError(retry, "HTTP 429") from exc
            raise RuntimeError(f"HTTP {exc.code}") from exc
        if isinstance(body, dict) and body.get("error"):
            error = body["error"]
            message = error.get("message", "API error") if isinstance(error, dict) else str(error)
            raise RuntimeError(message)
        content = body["choices"][0]["message"]["content"]
        result = json.loads(content) if isinstance(content, str) else content
        if not isinstance(result, dict) or not isinstance(result.get("learn"), bool):
            raise ValueError("validator returned invalid decision")
        return result

    def process_one(self):
        """Validate one candidate, or return a durable cooldown/no-candidate result."""
        with self._lock:
            now = self.clock()
            state = self._load_state()
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
            self._save_rows(rows)
            state["next_allowed_at"] = self._iso(now + self.MIN_INTERVAL)
            state["backoff_seconds"] = 15
            state["last_success_at"] = self._iso(now)
            state["last_error"] = None
            self._save_state(state)
            return {"ok": True, "reason": "reviewed", "proposal_id": row.get("proposal_id"), "learn": result["learn"], "status": self.status()}


__all__ = ["ChatGPTReviewWorker", "RateLimitError"]
