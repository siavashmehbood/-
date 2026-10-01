"""Tamper-evident, append-only audit journal for learning decisions.

The journal is observational only: it never authorizes learning and is never
used to change Learning Gate state.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from persistence import StateCorruptionError, json_transaction, load_critical_json


class ReviewDecisionJournal:
    ZERO_HASH = "0" * 64
    REVIEWER_DECISIONS = {"learn", "reject"}
    HUMAN_DECISIONS = {"approved", "rejected"}

    def __init__(self, path):
        self.path = Path(path)

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
        return {"valid": True, "count": count, "appended": appended, "head_hash": previous}

    def status(self):
        events = load_critical_json(self.path, [])
        head = self._validate(events)
        return {"valid": True, "count": len(events), "head_hash": head}


__all__ = ["ReviewDecisionJournal"]
