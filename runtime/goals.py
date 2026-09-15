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
                'created_at': datetime.now().isoformat(timespec='seconds')}
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

    def complete(self, goal_id):
        return self.update(goal_id, status='completed')
