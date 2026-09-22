"""Explicit user-controlled network access for IRAN."""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from persistence import atomic_write_json


class InternetAccessManager:
    """Project-level network permission; separate from durable-learning approval."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.enabled = False
        self.mode = "off"
        self.failure_reason = None
        self._load()

    def _load(self):
        # Permission differs from learned data: a backup can predate revocation.
        # Only the current primary may authorize network access after restart.
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('enabled'), bool):
                raise ValueError('permission must be a boolean')
            enabled = data['enabled']
            mode = 'on' if enabled else 'off'
            if data.get('mode', mode) != mode:
                raise ValueError('inconsistent permission mode')
            self.enabled, self.mode = enabled, mode
        except (OSError, ValueError, TypeError):
            self.enabled, self.mode = False, 'off'
            self.failure_reason = 'permission_state_unreadable'

    def _save(self):
        payload = {"enabled": self.enabled, "mode": self.mode}
        atomic_write_json(self.path, payload)

    def status(self):
        with self._lock:
            return {"enabled": self.enabled, "mode": self.mode,
                    "scope": "project", "learning_approval_separate": True,
                    "failure_reason": self.failure_reason}

    def _set_enabled(self, enabled):
        with self._lock:
            self.enabled, self.mode = enabled, 'on' if enabled else 'off'
            try:
                self._save()
            except OSError:
                self.enabled, self.mode = False, 'off'
                self.failure_reason = 'permission_write_failed'
                raise
            self.failure_reason = None
            return self.status()

    def enable(self):
        return self._set_enabled(True)

    def disable(self):
        return self._set_enabled(False)

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
