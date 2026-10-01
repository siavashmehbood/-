"""Tamper-evident, append-only audit journal for learning decisions.

The journal is observational only: it never authorizes learning and is never
used to change Learning Gate state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from persistence import StateCorruptionError, json_transaction


class ReviewDecisionJournal:
    ZERO_HASH = "0" * 64
    _UNVALIDATED = object()
    REVIEWER_DECISIONS = {"learn", "reject"}
    HUMAN_DECISIONS = {"approved", "rejected"}

    def __init__(self, path):
        self.path = Path(path)
        self._validated_fingerprint = self._UNVALIDATED
        self._validated_count = 0
        self._validated_head = self.ZERO_HASH
        self._validated_source = "empty"


    @staticmethod
    def _stat_fingerprint(path):
        try:
            stat = path.stat()
            return (stat.st_dev, stat.st_ino, stat.st_size,
                    stat.st_mtime_ns, stat.st_ctime_ns)
        except FileNotFoundError:
            return None

    def _fingerprint(self):
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        return (self._stat_fingerprint(self.path),
                self._stat_fingerprint(backup))

    def _load_with_source(self):
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        present = False
        for source, candidate in (("primary", self.path), ("backup", backup)):
            if not candidate.exists():
                continue
            present = True
            try:
                events = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError):
                continue
            if isinstance(events, list):
                return events, source
        if present:
            raise StateCorruptionError(
                "Unreadable durable state: " + str(self.path)
            )
        return [], "empty"

    def _load_stable(self):
        for _ in range(3):
            before = self._fingerprint()
            events, source = self._load_with_source()
            after = self._fingerprint()
            if before == after:
                return events, after, source
        raise StateCorruptionError(
            "Decision journal changed repeatedly during read: " + str(self.path)
        )

    def _remember_validation(self, fingerprint, events, head, source):
        self._validated_fingerprint = fingerprint
        self._validated_count = len(events)
        self._validated_head = head
        self._validated_source = source

    def _validated_events(self):
        events, fingerprint, source = self._load_stable()
        if fingerprint != self._validated_fingerprint:
            head = self._validate(events)
            self._remember_validation(fingerprint, events, head, source)
        return events

    @staticmethod
    def _hash(event):
        payload = {key: value for key, value in event.items() if key != "event_hash"}
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _validate(self, events):
        if not isinstance(events, list):
            raise StateCorruptionError("Decision journal must be a list: " + str(self.path))
        previous = self.ZERO_HASH
        keys = set()
        for index, event in enumerate(events, start=1):
            if not isinstance(event, dict):
                raise StateCorruptionError("Invalid decision journal event: " + str(self.path))
            actor = event.get("actor")
            decision = event.get("decision")
            proposal_id = str(event.get("proposal_id", ""))
            event_key = f"{actor}:{proposal_id}"
            allowed = self.REVIEWER_DECISIONS if actor == "reviewer" else self.HUMAN_DECISIONS
            valid = (
                actor in {"reviewer", "human"}
                and bool(proposal_id)
                and decision in allowed
                and event.get("version") == 1
                and event.get("sequence") == index
                and event.get("event_key") == event_key
                and event.get("previous_hash") == previous
                and event.get("event_hash") == self._hash(event)
                and event_key not in keys
            )
            if not valid:
                raise StateCorruptionError("Decision journal integrity check failed: " + str(self.path))
            keys.add(event_key)
            previous = event["event_hash"]
        return previous

    @staticmethod
    def _source_events(rows):
        for row in rows:
            proposal_id = str(row.get("proposal_id", ""))
            if not proposal_id:
                continue
            reviewer = row.get("chatgpt_decision")
            if row.get("review_status") == "reviewed" and reviewer in {"learn", "reject"}:
                yield {
                    "proposal_id": proposal_id,
                    "actor": "reviewer",
                    "decision": reviewer,
                    "decided_at": str(row.get("reviewed_at") or ""),
                    "provider": str(row.get("provider") or ""),
                    "model": str(row.get("model") or ""),
                }
            human = row.get("human_decision")
            if human in {"approved", "rejected"}:
                yield {
                    "proposal_id": proposal_id,
                    "actor": "human",
                    "decision": human,
                    "decided_at": str(row.get("human_decided_at") or ""),
                    "provider": "",
                    "model": "",
                }

    def sync(self, review_rows):
        """Append missing ledger decisions without making them authoritative."""
        if not isinstance(review_rows, list):
            raise StateCorruptionError("Review ledger must be a list: " + str(self.path))
        appended = 0
        with json_transaction(self.path, []) as events:
            previous = self._validate(events)
            by_key = {event["event_key"]: event for event in events}
            for source in self._source_events(review_rows):
                event_key = f"{source['actor']}:{source['proposal_id']}"
                existing = by_key.get(event_key)
                if existing is not None:
                    if existing.get("decision") != source["decision"]:
                        raise StateCorruptionError(
                            "Decision journal conflicts with review ledger: " + event_key
                        )
                    continue
                event = {
                    "version": 1,
                    "sequence": len(events) + 1,
                    "event_key": event_key,
                    **source,
                    "previous_hash": previous,
                }
                event["event_hash"] = self._hash(event)
                events.append(event)
                by_key[event_key] = event
                previous = event["event_hash"]
                appended += 1
            count = len(events)
        self._validated_fingerprint = self._UNVALIDATED
        return {"valid": True, "count": count, "appended": appended, "head_hash": previous}


    def page(self, limit=50, cursor=None):
        """Return a stable newest-first page after validating the full chain."""
        events = self._validated_events()
        limit = max(0, int(limit))
        if cursor is None:
            start = len(events) - 1
        else:
            cursor = str(cursor)
            start = next(
                (index - 1 for index, event in enumerate(events)
                 if event.get("event_hash") == cursor),
                None,
            )
            if start is None:
                raise ValueError("unknown decision journal cursor")
        if limit == 0 or start < 0:
            return {"items": [], "next_cursor": None, "count": len(events)}
        stop = max(-1, start - limit)
        items = [dict(events[index]) for index in range(start, stop, -1)]
        next_cursor = (
            items[-1]["event_hash"]
            if items and int(items[-1]["sequence"]) > 1
            else None
        )
        return {"items": items, "next_cursor": next_cursor, "count": len(events)}

    @staticmethod
    def _status_payload(count, head, source):
        return {
            "valid": True,
            "count": count,
            "head_hash": head,
            "source": source,
            "recovered_from_backup": source == "backup",
        }

    def status(self):
        fingerprint = self._fingerprint()
        if fingerprint == self._validated_fingerprint:
            return self._status_payload(
                self._validated_count, self._validated_head,
                self._validated_source,
            )
        events, fingerprint, source = self._load_stable()
        head = self._validate(events)
        self._remember_validation(fingerprint, events, head, source)
        return self._status_payload(len(events), head, source)


__all__ = ["ReviewDecisionJournal"]
