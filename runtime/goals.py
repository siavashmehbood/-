import json
from pathlib import Path
from datetime import datetime
from persistence import atomic_write_json, load_json_with_backup


class GoalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text('[]', encoding='utf-8')

    def _load(self):
        return load_json_with_backup(self.path, [])

    def _save(self, items):
        atomic_write_json(self.path, items)

    def add(self, title):
        items = self._load()
        next_id = max((int(item.get('id', 0)) for item in items), default=0) + 1
        item = {'id': next_id, 'title': title, 'status': 'active',
                'created_at': datetime.now().isoformat(timespec='seconds'),
                'attempts': 0, 'evidence': [], 'outcome': {}, 'learning': {},
                'updated_at': datetime.now().isoformat(timespec='seconds')}
        items.append(item)
        self._save(items)
        return item

    def list(self, status=None):
        items = self._load()
        if status is None:
            return items
        return [item for item in items if item.get('status') == status]

    def update(self, goal_id, **changes):
        items = self._load()
        allowed = {'title', 'status'}
        for item in items:
            if item['id'] == int(goal_id):
                for key, value in changes.items():
                    if key in allowed and value is not None:
                        item[key] = value
                item['updated_at'] = datetime.now().isoformat(timespec='seconds')
                self._save(items)
                return item
        return None

    def record_attempt(self, goal_id, evidence=None):
        items = self._load()
        for item in items:
            if item['id'] == int(goal_id):
                item['attempts'] = int(item.get('attempts', 0)) + 1
                if evidence is not None:
                    item.setdefault('evidence', []).append(evidence)
                    item['evidence'] = item['evidence'][-50:]
                item['updated_at'] = datetime.now().isoformat(timespec='seconds')
                self._save(items)
                return item
        return None

    def record_evidence(self, goal_id, evidence):
        return self.record_attempt(goal_id, evidence)

    def record_outcome(self, goal_id, success, result=None, score=0.0):
        items = self._load()
        for item in items:
            if item['id'] == int(goal_id):
                item['status'] = 'completed' if bool(success) else 'failed'
                item['outcome'] = {
                    'success': bool(success), 'result': result,
                    'score': max(0.0, min(1.0, float(score))),
                    'at': datetime.now().isoformat(timespec='seconds')}
                item['updated_at'] = datetime.now().isoformat(timespec='seconds')
                self._save(items)
                return item
        return None

    def record_learning(self, goal_id, learning):
        items = self._load()
        for item in items:
            if item['id'] == int(goal_id):
                item['learning'] = learning if isinstance(learning, dict) else {'value': learning}
                item['updated_at'] = datetime.now().isoformat(timespec='seconds')
                self._save(items)
                return item
        return None

    def complete(self, goal_id):
        return self.update(goal_id, status='completed')
