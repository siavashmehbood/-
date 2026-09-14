import json
from datetime import datetime
from pathlib import Path

class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event, data=None):
        record = {
            'time': datetime.now().isoformat(timespec='seconds'),
            'event': event,
            'data': data or {},
        }
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        return record

    def recent(self, limit=20):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding='utf-8').splitlines()
        return [json.loads(x) for x in lines[-limit:]]
