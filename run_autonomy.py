"""Run IRAN's local autonomous supervisor from the command line."""
from pathlib import Path
import argparse
import json
from runtime.app import IranRuntime


def main():
    parser = argparse.ArgumentParser(description="IRAN autonomous cognitive runtime")
    parser.add_argument('--cycles', type=int, default=10)
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--interval', type=int, default=10)
    args = parser.parse_args()
    runtime = IranRuntime(Path(__file__).resolve().parent)
    try:
        if args.daemon:
            runtime.start_autonomous_daemon(args.interval)
            print(json.dumps({'status': 'running', 'interval': args.interval}, ensure_ascii=False))
            input('Press Enter to stop... ')
            runtime.stop_autonomous_daemon()
        else:
            reports = runtime.autonomous_supervisor_run(args.cycles)
            print(json.dumps(reports[-1] if reports else {}, ensure_ascii=False, indent=2))
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
