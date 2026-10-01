from pathlib import Path
import runpy, sys, traceback
ROOT = Path(__file__).resolve().parent
LOG = ROOT / 'gui_startup.log'
with LOG.open('a', encoding='utf-8') as f:
    sys.stdout = f
    sys.stderr = f
    try:
        runpy.run_path(str(ROOT / 'gui.py'), run_name='__main__')
    except BaseException:
        traceback.print_exc(file=f)
        f.flush()
        raise
