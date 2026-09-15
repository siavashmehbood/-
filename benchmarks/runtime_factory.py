"""Self-contained runtime root for benchmarks and audits.

`IranRuntime` expects a writable root containing `config.json` plus `data/` and
`logs/` directories; those are gitignored in the repository, so callers must
materialise them. Keeping this here means the benchmark, the audit script and
the CI workflow all build their root the same way.
"""
import json
import shutil
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_isolated_root():
    root = Path(tempfile.mkdtemp(prefix='iran_benchmark_'))
    config = json.loads((PROJECT_ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    config['memory']['db'] = 'data/benchmark.db'
    config['runtime']['event_log'] = 'logs/benchmark.jsonl'
    config['runtime']['goals'] = 'data/goals.json'
    (root / 'data').mkdir()
    (root / 'logs').mkdir()
    (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    return root


def isolated_runtime_factory():
    from runtime.app import IranRuntime

    class IsolatedRuntime(IranRuntime):
        def __init__(self):
            self._root_dir = make_isolated_root()
            super().__init__(self._root_dir)

        def close(self):
            try:
                super().close()
            finally:
                shutil.rmtree(self._root_dir, ignore_errors=True)

    return IsolatedRuntime
