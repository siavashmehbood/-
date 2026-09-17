from pathlib import Path
from core.programming_learner import LocalCodeSandbox, ProgrammingLearner


def test_sandbox_runs_and_verifies():
    sandbox = LocalCodeSandbox()
    out, err, rc, elapsed = sandbox.run('print("OK")')
    assert (out, err, rc) == ("OK", "", 0)
    assert elapsed >= 0


def test_curriculum_learns_from_verified_execution(tmp_path):
    learner = ProgrammingLearner(tmp_path)
    report = learner.practice(cycles=7)
    assert len(report) == 7
    assert all(item["attempt"]["passed"] for item in report)
    assert learner.status()["completed"] == 7
    assert learner.next_lesson() is None


def test_sandbox_blocks_dangerous_imports():
    sandbox = LocalCodeSandbox()
    try:
        sandbox.run("import os\nprint(os.getcwd())")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe import was not blocked")
