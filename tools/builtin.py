from datetime import datetime
from pathlib import Path
import json
import platform
import urllib.request
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

    def calculate(expression):
        """Evaluate a tiny arithmetic expression without eval or external code."""
        import ast
        import operator

        text = str(expression).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٫', '0123456789.'))
        text = text.replace('×', '*').replace('÷', '/').replace('−', '-')
        tree = ast.parse(text, mode='eval')
        binary = {
            ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
            ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod, ast.Pow: operator.pow,
        }
        unary = {ast.UAdd: operator.pos, ast.USub: operator.neg}

        def visit(node):
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in binary:
                left, right = visit(node.left), visit(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 12:
                    raise ValueError('توان خارج از محدوده محاسبه محلی است')
                value = binary[type(node.op)](left, right)
                if abs(value) > 10**15:
                    raise ValueError('نتیجه خارج از محدوده محاسبه محلی است')
                return value
            if isinstance(node, ast.UnaryOp) and type(node.op) in unary:
                return unary[type(node.op)](visit(node.operand))
            raise ValueError('عبارت محاسباتی پشتیبانی نمی‌شود')

        value = visit(tree)
        return int(value) if isinstance(value, float) and value.is_integer() else value

    registry.register(Tool('calculate', 'محاسبات عددی پایه و امن', calculate, safe=True, permission='read'))

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

    from security.experiment import run_experiment
    sandbox_python = run_experiment

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

    from .desktop import DesktopTools, InputController, WindowsDesktop
    desktop, inputs, windows = DesktopTools(root), InputController(), WindowsDesktop(root)
    registry.register(Tool('find_file', 'جستجوی فایل در محدوده پروژه', desktop.find_file, True, 'read'))
    registry.register(Tool('open_file', 'باز کردن فایل موجود در محدوده پروژه', desktop.open_file, False, 'execute'))
    registry.register(Tool('open_folder', 'باز کردن پوشه موجود در محدوده پروژه', desktop.open_folder, False, 'execute'))
    registry.register(Tool('get_battery', 'وضعیت باتری سیستم', desktop.battery, True, 'read'))
    registry.register(Tool('get_volume', 'قابلیت کنترل صدای Windows', desktop.volume, True, 'read'))
    registry.register(Tool('set_volume', 'کم/زیاد/قطع کردن صدای Windows', desktop.change_volume, False, 'input_control'))
    registry.register(Tool('create_folder', 'ساخت پوشه در محدوده پروژه', desktop.create_folder, False, 'write'))
    registry.register(Tool('copy_file', 'کپی فایل در محدوده پروژه', desktop.copy_file, False, 'write'))
    registry.register(Tool('move_file', 'انتقال فایل در محدوده پروژه', desktop.move_file, False, 'write'))
    registry.register(Tool('rename_file', 'تغییر نام فایل در محدوده پروژه', desktop.rename_file, False, 'write'))
    registry.register(Tool('open_application', 'اجرای برنامه دسکتاپ در Windows', desktop.open_application, False, 'execute'))
    registry.register(Tool('close_application', 'بستن برنامه با شناسه فرایند', desktop.close_application, False, 'destructive'))
    registry.register(Tool('list_running_apps', 'فهرست برنامه‌های در حال اجرا', desktop.list_running_apps, True, 'read'))
    registry.register(Tool('screenshot', 'ثبت تصویر واقعی صفحه', desktop.screenshot, True, 'read'))
    registry.register(Tool('active_window', 'پنجره فعال Windows', windows.active_window, True, 'read'))
    registry.register(Tool('list_windows', 'فهرست پنجره‌های قابل مشاهده Windows', windows.enumerate_windows, True, 'read'))
    registry.register(Tool('find_window', 'پیدا کردن پنجره با عنوان معنایی', windows.find_window, True, 'read'))
    registry.register(Tool('window_text', 'خواندن متن قابل مشاهده child controls پنجره', windows.window_text, True, 'read'))
    registry.register(Tool('automation_text', 'خواندن متن کنترل Windows با پیام native', windows.automation_text, True, 'read'))
    registry.register(Tool('uia_elements', 'مشاهده ساختاری عناصر Windows UI Automation', windows.uia_elements, True, 'read'))
    registry.register(Tool('uia_text', 'خواندن متن Windows UI Automation ValuePattern', windows.uia_text, True, 'read'))
    registry.register(Tool('uia_document_text', 'خواندن محتوای Document/Edit از Windows UI Automation', windows.uia_document_text, True, 'read'))
    registry.register(Tool('uia_type_text', 'تایپ در Document/Edit grounded با Windows UI Automation', windows.uia_set_and_read_text, False, 'input_control'))
    registry.register(Tool('focus_window', 'تمرکز روی پنجره Windows', windows.focus, False, 'input_control'))
    registry.register(Tool('minimize_window', 'کوچک کردن پنجره Windows', windows.minimize, False, 'input_control'))
    registry.register(Tool('maximize_window', 'بزرگ کردن پنجره Windows', windows.maximize, False, 'input_control'))
    registry.register(Tool('restore_window', 'بازیابی پنجره Windows', windows.restore, False, 'input_control'))
    registry.register(Tool('clipboard_read', 'خواندن clipboard', windows.clipboard_read, True, 'read'))
    registry.register(Tool('clipboard_write', 'نوشتن clipboard', windows.clipboard_write, False, 'write'))
    registry.register(Tool('mouse_move', 'حرکت نشانگر ماوس', inputs.move, False, 'input_control'))
    registry.register(Tool('mouse_click', 'کلیک ماوس', inputs.click, False, 'input_control'))
    registry.register(Tool('mouse_scroll', 'اسکرول ماوس', inputs.scroll, False, 'input_control'))
    registry.register(Tool('keyboard_type', 'تایپ با صفحه‌کلید', inputs.type_text, False, 'input_control'))
    registry.register(Tool('key_press', 'فشردن کلید', inputs.press, False, 'input_control'))
    registry.register(Tool('hotkey', 'فشردن ترکیب کلیدها', inputs.hotkey, False, 'input_control'))
    return registry
