"""Explicit user-controlled network access for IRAN."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from persistence import atomic_write_json, load_json_with_backup


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
            data = load_json_with_backup(self.path, {})
            # Network permission is intentionally session-scoped by default.
            self.enabled = bool(data.get("enabled", False))
            self.mode = "on" if self.enabled else "off"
        except (OSError, ValueError, TypeError):
            self.enabled = False
            self.mode = "off"

    def _save(self):
        payload = {"enabled": self.enabled, "mode": self.mode}
        atomic_write_json(self.path, payload)

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


def validate_public_url(url):
    """Evidence retrieval never targets local services or URLs carrying credentials."""
    from urllib.parse import urlsplit
    import socket, ipaddress
    parsed = urlsplit(str(url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("invalid_source_url")
    if parsed.port not in {None,80,443}: raise ValueError("source_port_not_allowed")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("private_source_address")
    return str(url)
