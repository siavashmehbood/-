import json
import subprocess
import sys
import time
from pathlib import Path

from security.learning_gate import LearningGate


ROOT = Path(__file__).parents[1]
CHILD = r"""
import json
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
deadline = time.monotonic() + 30
while not start_path.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("parallel LearningGate start signal was not created")
    time.sleep(0.01)
row = gate.request(
    "knowledge.add_fact",
    {"claim": claim, "nested": {"source": "parallel fixture"}},
    "parallel fixture",
)
print(json.dumps({"claim": claim, "proposal_id": row["proposal_id"]}))
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

        deadline = time.monotonic() + 30
        while not all(ready.exists() for _, ready in children):
            assert time.monotonic() < deadline, (
                "child processes did not reach the start barrier"
            )
            time.sleep(0.01)
        start_path.write_text("start", encoding="utf-8")

        outputs = []
        failures = []
        for child, _ in children:
            stdout, stderr = child.communicate(timeout=30)
            if child.returncode != 0:
                failures.append((child.returncode, stdout, stderr))
            else:
                outputs.append(json.loads(stdout))
        assert failures == []
    finally:
        for child, _ in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    gate = LearningGate(gate_path)
    rows = gate.history(100)

    assert len(rows) == 5
    assert gate.stats() == {
        "pending": 5,
        "approved": 0,
        "rejected": 0,
        "total": 5,
        "requests": 5,
        "xp_units": 5,
        "xp": 5_000_000,
    }
    assert {row["payload"]["claim"] for row in rows} == {
        "shared",
        "unique-0",
        "unique-1",
        "unique-2",
        "unique-3",
    }
    assert sum(row["payload"]["claim"] == "shared" for row in rows) == 1

    shared_ids = {
        row["proposal_id"] for row in outputs if row["claim"] == "shared"
    }
    assert len(shared_ids) == 1
    assert shared_ids == {
        row["proposal_id"]
        for row in rows
        if row["payload"]["claim"] == "shared"
    }

# Final master validation marker for Windows/Linux LearningGate lock fix.
