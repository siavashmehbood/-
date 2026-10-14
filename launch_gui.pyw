from pathlib import Path
import os, runpy, sys, traceback

ROOT = Path(__file__).resolve().parent
LOG = ROOT / 'gui_startup.log'

def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        runpy.run_path(str(ROOT / 'gui.py'), run_name='__main__')
    except Exception:
        with LOG.open('a', encoding='utf-8') as stream:
            traceback.print_exc(file=stream)
        print("IRAN could not start. Check gui_startup.log; install requirements-dev.txt "
              "and close another IRAN instance using this data folder.", file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
