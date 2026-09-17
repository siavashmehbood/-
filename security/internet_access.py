"""Explicit user-controlled network access for IRAN."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock


class InternetAccessManager:
    """Project-level network permission; separate from durable-learning approval."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.enabled = False
        self.mode = "off"
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            # Network permission is intentionally session-scoped by default.
            self.enabled = bool(data.get("enabled", False))
            self.mode = "on" if self.enabled else "off"
        except (OSError, ValueError, TypeError):
            self.enabled = False
            self.mode = "off"

    def _save(self):
        payload = {"enabled": self.enabled, "mode": self.mode}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self):
        with self._lock:
            return {"enabled": self.enabled, "mode": self.mode,
                    "scope": "project", "learning_approval_separate": True}

    def enable(self):
        with self._lock:
            self.enabled = True
            self.mode = "on"
            self._save()
            return self.status()

    def disable(self):
        with self._lock:
            self.enabled = False
            self.mode = "off"
            self._save()
            return self.status()

    def require(self):
        with self._lock:
            if not self.enabled:
                raise PermissionError(
                    "internet_access_denied: enable IRAN internet access first"
                )
