from datetime import datetime
from pathlib import Path
import json
import platform
import urllib.request
import subprocess
import tempfile
import sys
import re
from .registry import Tool, ToolRegistry


def build_registry(root, memory, internet_access=None):
    registry = ToolRegistry()
    root = Path(root)

    def require_internet():
        if internet_access is not None:
            internet_access.require()

    registry.register(Tool('time_now', 'زمان و تاریخ سیستم', lambda: datetime.now().isoformat(timespec='seconds'), safe=True, permission='read'))
    registry.register(Tool('memory_search', 'جستجوی حافظه', lambda query, limit=8: memory.search(query, int(limit)), safe=True, permission='read'))

    def project_files(pattern='*'):
        return [str(p.relative_to(root)) for p in root.rglob(pattern) if p.is_file() and 'sandbox' not in p.parts and '__pycache__' not in p.parts]
    registry.register(Tool('project_files', 'فهرست فایل‌های پروژه', project_files, safe=True, permission='read'))

    def read_project_file(path, max_chars=12000):
        target = (root / str(path)).resolve()
        if root.resolve() not in target.parents and target != root.resolve():
            raise PermissionError('مسیر خارج از پروژه مجاز نیست')
        if not target.is_file():
            raise FileNotFoundError(str(path))
        return target.read_text(encoding='utf-8', errors='replace')[:int(max_chars)]
    registry.register(Tool('read_project_file', 'خواندن فایل پروژه بدون تغییر', read_project_file, safe=True, permission='read'))

    def system_info():
        return {'platform': platform.platform(), 'python': platform.python_version(), 'machine': platform.machine()}
    registry.register(Tool('system_info', 'اطلاعات پایه سیستم', system_info, safe=True, permission='read'))

    def project_summary():
        counts = {}
        for p in root.rglob('*'):
            if p.is_file() and 'sandbox' not in p.parts and '__pycache__' not in p.parts:
                ext = p.suffix.lower() or '[no-extension]'
                counts[ext] = counts.get(ext, 0) + 1
        return {'files': sum(counts.values()), 'by_extension': counts}
    registry.register(Tool('project_summary', 'خلاصه ساختار پروژه', project_summary, safe=True, permission='read'))

    def sandbox_python(code, timeout=5):
        """Run a generated, deterministic experiment in an isolated temporary directory."""
        code = str(code)
        if len(code) > 12000:
            raise ValueError('sandbox code too large')
        blocked = re.compile(r'(?i)\\b(import\\s+(os|sys|subprocess|socket|shutil|pathlib|ctypes)|from\\s+(os|sys|subprocess|socket|shutil|pathlib|ctypes)|open\\s*\\(|exec\\s*\\(|eval\\s*\\(|__import__|socket\\.|subprocess\\.|os\\.)')
        if blocked.search(code):
            raise PermissionError('sandbox rejected unsafe operation')
        with tempfile.TemporaryDirectory(prefix='iran-exp-') as td:
            script = Path(td) / 'experiment.py'
            script.write_text(code, encoding='utf-8')
            env = {'PATH': str(Path(sys.executable).parent), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
            proc = subprocess.run([sys.executable, '-I', '-S', str(script)], cwd=td,
                                  env=env, capture_output=True, text=True, timeout=max(1, min(15, int(timeout))))
            return {'ok': proc.returncode == 0, 'returncode': proc.returncode,
                    'stdout': proc.stdout[-8000:], 'stderr': proc.stderr[-4000:]}

    registry.register(Tool('sandbox_python', 'اجرای آزمایش محدود و بدون تغییر پروژه', sandbox_python, safe=True, permission='execute'))

    def web_fetch(url, max_chars=8000):
        require_internet()
        if not str(url).lower().startswith(('http://', 'https://')):
            raise ValueError('فقط URLهای http/https مجاز هستند')
        req = urllib.request.Request(str(url), headers={'User-Agent': 'IranAI/0.9'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read(int(max_chars)).decode('utf-8', errors='replace')
    registry.register(Tool('web_fetch', 'دریافت متن از URL عمومی', web_fetch, safe=True, permission='network'))

    def save_note(title, content):
        path = root / 'data' / 'notes.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'time': datetime.now().isoformat(timespec='seconds'), 'title': str(title), 'content': str(content)}
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        return record
    registry.register(Tool('save_note', 'ذخیره یادداشت کاربر', save_note, safe=False, permission='write'))
    return registry
