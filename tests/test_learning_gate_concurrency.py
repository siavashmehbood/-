import subprocess
import sys
import time
from pathlib import Path

from security.learning_gate import LearningGate


ROOT = Path(__file__).parents[1]
CHILD = r"""
import sys
import time
from pathlib import Path
from security.learning_gate import LearningGate

gate_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
start_path = Path(sys.argv[3])
claim = sys.argv[4]
gate = LearningGate(gate_path)
ready_path.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 15
while not start_path.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("parallel learning-gate start signal was not created")
    time.sleep(0.01)
gate.request("knowledge.add_fact", {"claim": claim}, "parallel fixture")
"""


def test_parallel_process_requests_are_deduplicated_without_lost_rows(tmp_path):
    gate_path = tmp_path / "proposals.json"
    start_path = tmp_path / "start"
    claims = ["shared"] * 4 + [f"unique-{index}" for index in range(4)]
    children = []

    try:
        for index, claim in enumerate(claims):
            ready_path = tmp_path / f"ready-{index}"
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    CHILD,
                    str(gate_path),
                    str(ready_path),
                    str(start_path),
                    claim,
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            children.append((child, ready_path))

        deadline = time.monotonic() + 15
        while not all(ready.exists() for _, ready in children):
            assert time.monotonic() < deadline, "child processes did not reach the start barrier"
            time.sleep(0.01)
        start_path.write_text("start", encoding="utf-8")

        failures = []
        for child, _ in children:
            stdout, stderr = child.communicate(timeout=20)
            if child.returncode != 0:
                failures.append((child.returncode, stdout, stderr))
        assert failures == []
    finally:
        for child, _ in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    rows = LearningGate(gate_path).history(100)
    assert len(rows) == 5
    assert {row["payload"]["claim"] for row in rows} == {
        "shared",
        "unique-0",
        "unique-1",
        "unique-2",
        "unique-3",
    }
    assert sum(row["payload"]["claim"] == "shared" for row in rows) == 1
