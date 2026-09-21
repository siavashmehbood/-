from persistence import atomic_write_json, load_critical_json
import json
from pathlib import Path
from datetime import datetime


class ProceduralMemory:
    """Durable structured procedures derived from verified experience."""
    def __init__(self, path, gate=None):
        self.path = Path(path); self.gate = gate
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.procedures = []
        self._load()

    def _load(self):
        self.procedures = load_critical_json(self.path, [])[-5000:]

    def _save(self):
        atomic_write_json(self.path, self.procedures)

    def upsert(self, name, goal, steps, preconditions=None, expected_outcome='',
               verification_conditions=None, failure_conditions=None, source_experiences=None,
               confidence=.6, success_rate=0., procedure_id=None):
        now = datetime.now().isoformat(timespec='seconds')
        pid = procedure_id or self._stable_id(name, goal)
        row = next((x for x in self.procedures if x.get('procedure_id') == pid), None)
        payload = {'procedure_id': pid, 'name': str(name), 'goal': str(goal),
                   'preconditions': list(preconditions or []), 'steps': list(steps or []),
                   'expected_outcome': str(expected_outcome),
                   'verification_conditions': list(verification_conditions or []),
                   'failure_conditions': list(failure_conditions or []),
                   'source_experiences': list(source_experiences or []),
                   'success_rate': round(float(success_rate), 4), 'confidence': round(float(confidence), 4),
                   'created_at': row.get('created_at', now) if row else now, 'updated_at': now}
        if self.gate is not None:
            proposal=self.gate.request('procedural.upsert',payload,f'Procedure: {name}')
            if proposal is not None: return proposal
        if row: row.update(payload)
        else: self.procedures.append(payload)
        self._save()
        return payload

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
        if self.gate is not None:
            proposal=self.gate.request('procedural.record_outcome',{'procedure_id':procedure_id,'success':bool(success)},f'Update procedure outcome: {procedure_id}')
            if proposal is not None: return proposal
        old = float(row.get('success_rate', 0)); row['success_rate'] = round(old * .8 + (1.0 if success else 0.0) * .2, 4)
        row['confidence'] = round(max(.05, min(.99, float(row.get('confidence', .5)) + (.03 if success else -.08))), 4)
        row['updated_at'] = datetime.now().isoformat(timespec='seconds'); self._save(); return row
