import json
from pathlib import Path
from datetime import datetime


class ProceduralMemory:
    """Durable structured procedures derived from verified experience."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.procedures = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.procedures = json.loads(self.path.read_text(encoding='utf-8'))[-5000:]
            except Exception:
                self.procedures = []

    def _save(self):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.procedures, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    def upsert(self, name, goal, steps, preconditions=None, expected_outcome='',
               verification_conditions=None, failure_conditions=None, source_experiences=None,
               confidence=.6, success_rate=0., procedure_id=None):
        now = datetime.now().isoformat(timespec='seconds')
        pid = procedure_id or self._stable_id(name, goal)
        row = next((x for x in self.procedures if x.get('procedure_id') == pid), None)
        previous_version = int(row.get('version', 0)) if row else 0
        version = previous_version + 1 if row else 1
        payload = {'procedure_id': pid, 'name': str(name), 'goal': str(goal),
                   'preconditions': list(preconditions or []), 'steps': list(steps or []),
                   'expected_outcome': str(expected_outcome),
                   'verification_conditions': list(verification_conditions or []),
                   'failure_conditions': list(failure_conditions or []),
                   'source_experiences': list(source_experiences or []),
                   'success_rate': round(float(success_rate), 4), 'confidence': round(float(confidence), 4),
                   'version': version,
                   'created_at': row.get('created_at', now) if row else now, 'updated_at': now}
        if row:
            # A procedure is versioned, so a revision keeps the shape it replaced. Without
            # this, a change that lowered success_rate was unrecoverable and there was no
            # way to see whether the procedure is improving or being rewritten each run.
            history = row.setdefault('history', [])
            history.append({k: row.get(k) for k in payload if k != 'history'})
            del history[:-20]
            row.update(payload)
        else:
            payload['history'] = []
            self.procedures.append(payload)
        self._save()
        # Return a snapshot, not the live stored record. Returning the live dict meant a
        # caller holding the result saw it change under them when the same procedure was
        # revised or had an outcome recorded later, which made "what was stored at that
        # moment" impossible to reason about.
        return dict(payload)

    def revision_of(self, procedure_id, version=None):
        """Return a specific revision of a procedure, or the current one.

        Lets a caller inspect what a procedure looked like before it was changed, which
        is what makes 'versioned' meaningful rather than just a counter.
        """
        row = next((x for x in self.procedures if x.get('procedure_id') == procedure_id), None)
        if row is None:
            return None
        if version is None or int(version) == int(row.get('version', 1)):
            return row
        for entry in reversed(row.get('history', [])):
            if int(entry.get('version', 0)) == int(version):
                return entry
        return None

    def versions(self, procedure_id):
        """All known revisions of a procedure, oldest first."""
        row = next((x for x in self.procedures if x.get('procedure_id') == procedure_id), None)
        if row is None:
            return []
        history = list(row.get('history', []))
        current = {k: row.get(k) for k in row if k != 'history'}
        return history + [current]

    @staticmethod
    def _stable_id(name, goal):
        import hashlib
        return 'proc_' + hashlib.sha256((str(name) + '|' + str(goal)).encode('utf-8')).hexdigest()[:16]

    def retrieve(self, goal, limit=5):
        q = set(str(goal).lower().split())
        ranked = []
        for row in self.procedures:
            text = (row.get('goal', '') + ' ' + row.get('name', '')).lower()
            toks = set(text.split()); overlap = len(q & toks) / max(1, len(q))
            score = .65 * overlap + .35 * float(row.get('confidence', 0))
            if overlap or str(goal).strip() == row.get('goal', '').strip(): ranked.append((score, row))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in ranked[:int(limit)]]

    def check_preconditions(self, procedure, context=None):
        context = context or {}
        missing = [p for p in procedure.get('preconditions', []) if not self._condition(p, context)]
        return {'applicable': not missing, 'missing': missing}

    @staticmethod
    def _condition(condition, context):
        if not condition: return True
        text = str(condition).strip().lower()
        if text in {'true', 'always', 'evidence_available'}: return text != 'evidence_available' or bool(context.get('evidence'))
        return bool(context.get(text, False))

    def record_outcome(self, procedure_id, success):
        row = next((x for x in self.procedures if x.get('procedure_id') == procedure_id), None)
        if not row: return None
        old = float(row.get('success_rate', 0)); row['success_rate'] = round(old * .8 + (1.0 if success else 0.0) * .2, 4)
        row['confidence'] = round(max(.05, min(.99, float(row.get('confidence', .5)) + (.03 if success else -.08))), 4)
        row['updated_at'] = datetime.now().isoformat(timespec='seconds'); self._save(); return row
