import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.persian_conversation_benchmark import PersianConversationBenchmark
from runtime.app import IranRuntime


def main():
    runtime = IranRuntime(ROOT)
    try:
        benchmark = PersianConversationBenchmark()
        report = benchmark.run(runtime)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['score'] >= 90 else 1
    finally:
        runtime.close()


if __name__ == '__main__':
    raise SystemExit(main())
