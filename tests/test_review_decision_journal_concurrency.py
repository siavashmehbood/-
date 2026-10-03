import json
import subprocess
import sys
import time
from pathlib import Path

from security.review_decision_journal import ReviewDecisionJournal


ROOT = Path(__file__).parents[1]
CHILD = r"""
import json
import sys
import time
from pathlib import Path
from security.review_decision_journal import ReviewDecisionJournal

journal_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
start_path = Path(sys.argv[3])
proposal_id = sys.argv[4]
ready_path.write_text("ready", encoding="utf-8")
deadline = time.monotonic() + 15
while not start_path.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError("parallel journal start signal was not created")
    time.sleep(0.01)
row = {
    "proposal_id": proposal_id,
    "review_status": "reviewed",
    "chatgpt_decision": "learn",
    "reviewed_at": "2030-01-01T00:00:00+00:00",
    "provider": "fixture",
    "model": "openrouter/free",
}
result = ReviewDecisionJournal(journal_path).sync([row])
print(json.dumps(result))
"""


def test_parallel_sync_is_deduplicated_and_invalidates_parent_checkpoint(tmp_path):
    journal_path = tmp_path / "review_decision_journal.json"
    journal = ReviewDecisionJournal(journal_path)
    assert journal.status()["count"] == 0

    start_path = tmp_path / "start"
    proposal_ids = ["shared"] * 4 + [f"unique-{index}" for index in range(4)]
    children = []

    try:
        for index, proposal_id in enumerate(proposal_ids):
            ready_path = tmp_path / f"ready-{index}"
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    CHILD,
                    str(journal_path),
                    str(ready_path),
                    str(start_path),
                    proposal_id,
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            children.append((child, ready_path))

        deadline = time.monotonic() + 15
        while not all(ready.exists() for _, ready in children):
            assert time.monotonic() < deadline, (
                "child processes did not reach the start barrier"
            )
            time.sleep(0.01)
        start_path.write_text("start", encoding="utf-8")

        failures = []
        results = []
        for child, _ in children:
            stdout, stderr = child.communicate(timeout=20)
            if child.returncode != 0:
                failures.append((child.returncode, stdout, stderr))
            else:
                results.append(json.loads(stdout))
        assert failures == []
        assert len(results) == len(proposal_ids)
    finally:
        for child, _ in children:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    status = journal.status()
    page = journal.page(limit=100)
    assert status["valid"] is True
    assert status["count"] == 5
    assert page["count"] == 5
    assert [event["sequence"] for event in page["items"]] == [5, 4, 3, 2, 1]
    assert len({event["event_key"] for event in page["items"]}) == 5
    assert sum(
        event["proposal_id"] == "shared" for event in page["items"]
    ) == 1
