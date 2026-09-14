from datetime import datetime
import json
from pathlib import Path


class Scheduler:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return []

    def _save(self, items):
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')

    def add(self, title, run_at=None, repeat=None):
        items = self._load()
        item = {'id': len(items) + 1, 'title': title, 'run_at': run_at, 'repeat': repeat, 'enabled': True, 'created_at': datetime.now().isoformat(timespec='seconds')}
        items.append(item)
        self._save(items)
        return item

    def list(self, enabled=None):
        items = self._load()
        return [x for x in items if enabled is None or x.get('enabled') == enabled]

    def disable(self, item_id):
        items = self._load()
        for item in items:
            if item['id'] == int(item_id):
                item['enabled'] = False
                self._save(items)
                return item
        return None
