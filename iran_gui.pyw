import sys
import os
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
LOG = ROOT / 'logs' / 'gui_startup.log'
LOG.parent.mkdir(parents=True, exist_ok=True)

def log_exception(exc_type, exc_value, exc_tb):
    with LOG.open('a', encoding='utf-8') as f:
        f.write('\n--- GUI ERROR ---\n')
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)

sys.excepthook = log_exception

try:
    from PySide6.QtWidgets import QApplication
    from gui_pyside6 import ChatWindow
    app = QApplication(sys.argv)
    app.setApplicationName('IRAN Cognitive Workspace')
    win = ChatWindow()
    win.show()
    sys.exit(app.exec())
except Exception:
    with LOG.open('a', encoding='utf-8') as f:
        traceback.print_exc(file=f)
    raise
