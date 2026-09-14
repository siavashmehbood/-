import os
import sys
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
    from gui import launch
    launch()
except Exception:
    with LOG.open('a', encoding='utf-8') as f:
        traceback.print_exc(file=f)
    raise
