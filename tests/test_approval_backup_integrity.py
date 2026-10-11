import json
import sqlite3
import pytest
from learning.approval_transaction import recover


@pytest.mark.parametrize("backup", ["missing", "corrupt", "empty"])
def test_unusable_approval_backup_preserves_memory_and_recovery_evidence(tmp_path, backup):
    data = tmp_path / "data"
    data.mkdir()
    memory = data / "memory.db"
    with sqlite3.connect(memory) as conn:
        conn.execute("CREATE TABLE retained (value TEXT)")
        conn.execute("INSERT INTO retained VALUES ('original')")
    journal = data / "approval_checkpoint.json"
    state = {"status": "prepared", "memory": "data/memory.db", "files": {}, "rows": {}}
    journal.write_text(json.dumps(state), encoding="utf-8")
    source = data / "approval_memory.sqlite"
    if backup == "corrupt":
        source.write_bytes(b"not a SQLite database")
    elif backup == "empty":
        with sqlite3.connect(source) as conn:
            conn.execute("VACUUM")

    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        recover(tmp_path)

    assert json.loads(journal.read_text()) == state
    assert source.exists() == (backup != "missing")
    with sqlite3.connect(memory) as conn:
        assert conn.execute("SELECT value FROM retained").fetchall() == [("original",)]


@pytest.mark.parametrize("damage", [
    {"memory": None},
    {"files": None},
    {"rows": None},
    {"rows": {"data/gate.json": [None]}},
    {"rows": {"data/gate.json": [{"proposal_id": "same"}, {"proposal_id": "same"}]}},
])
def test_damaged_checkpoint_is_rejected_before_sqlite_rollback(tmp_path, damage):
    data = tmp_path / "data"
    data.mkdir()
    memory = data / "memory.db"
    with sqlite3.connect(memory) as conn:
        conn.execute("CREATE TABLE retained (value TEXT)")
        conn.execute("INSERT INTO retained VALUES ('current')")
    backup = data / "approval_memory.sqlite"
    with sqlite3.connect(backup) as conn:
        conn.execute("CREATE TABLE retained (value TEXT)")
        conn.execute("INSERT INTO retained VALUES ('old')")
    state = {"status": "prepared", "memory": "data/memory.db", "files": {}, "rows": {}}
    state.update(damage)
    journal = data / "approval_checkpoint.json"
    journal.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Invalid approval recovery checkpoint"):
        recover(tmp_path)
    with sqlite3.connect(memory) as conn:
        assert conn.execute("SELECT value FROM retained").fetchall() == [("current",)]
    assert json.loads(journal.read_text()) == state
    assert backup.exists()
