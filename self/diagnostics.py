from pathlib import Path
import shutil
import time


class Diagnostics:
    def __init__(self, root, brain, registry=None):
        self.root = Path(root)
        self.brain = brain
        self.registry = registry

    def run(self):
        disk = shutil.disk_usage(self.root.anchor)
        checks = {
            'project_exists': self.root.exists(),
            'config_exists': (self.root / 'config.json').exists(),
            'database_exists': (self.root / 'data' / 'iran.db').exists(),
            'brain_ok': bool(self.brain.health().get('ok')),
            'tools': len(self.registry.list()) if self.registry else 0,
            'free_gb': round(disk.free / 1024**3, 2),
        }
        checks['ok'] = all(checks[k] for k in ('project_exists', 'config_exists', 'brain_ok'))
        return checks
