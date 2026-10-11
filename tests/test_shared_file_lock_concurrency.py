"""Exercise shared persistence locks in real processes on Linux and Windows."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CHILD = r"""
import json
import sys
import time
from pathlib import Path
from persistence import file_lock, json_transaction

root = Path(sys.argv[1])
ready = root / ("ready-" + sys.argv[2])
ready.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 30
while not (root / "start").exists():
    if time.monotonic() > deadline:
        raise TimeoutError("start barrier timed out")
    time.sleep(.01)
for _ in range(20):
    with json_transaction(root / "counter.json", {"count": 0}) as state:
        state["count"] += 1
# A recursive acquisition must not release the outer process lock.
with file_lock(root / "counter.json.lock"):
    with file_lock(root / "counter.json.lock"):
        pass
print("ok")
"""


@pytest.mark.parametrize("existing_marker", [False, True])
def test_parallel_json_updates_have_no_lost_writes(tmp_path, existing_marker):
    if existing_marker:
        (tmp_path / "counter.json.lock").write_bytes(b"0")
    children = []
    try:
        for index in range(6):
            children.append(subprocess.Popen(
                [sys.executable, "-c", CHILD, str(tmp_path), str(index)],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        deadline = time.monotonic() + 30
        while not all((tmp_path / f"ready-{i}").exists() for i in range(6)):
            assert time.monotonic() < deadline, "children did not reach barrier"
            time.sleep(.01)
        (tmp_path / "start").write_text("start", encoding="utf-8")
        results = [child.communicate(timeout=30) for child in children]
        assert all(child.returncode == 0 for child in children), results
        assert all(stdout.strip() == "ok" for stdout, _ in results), results
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
    assert json.loads((tmp_path / "counter.json").read_text()) == {"count": 120}
    assert (tmp_path / "counter.json.lock").read_bytes() == b"0"


def test_recursive_lock_retains_exclusion_until_outer_exit(tmp_path):
    # Use a subprocess so an accidental self-deadlock fails with a timeout.
    code = r"""
import subprocess
import sys
from pathlib import Path
from persistence import file_lock, acquire_runtime_ownership, RuntimeAlreadyRunning

path = Path(sys.argv[1])
probe = r'''
import sys
from persistence import acquire_runtime_ownership, RuntimeAlreadyRunning
try:
    handle = acquire_runtime_ownership(sys.argv[1])
except RuntimeAlreadyRunning:
    sys.exit(7)
else:
    handle.close()
'''
with file_lock(path):
    with file_lock(path):
        pass
    contender = subprocess.run([sys.executable, "-c", probe, str(path)], timeout=10)
    assert contender.returncode == 7, contender.returncode
handle = acquire_runtime_ownership(path)
handle.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "shared.lock")],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
