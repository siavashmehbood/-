import json
import sqlite3
import pytest
from learning.approval_transaction import recover


@pytest.mark.parametrize("backup", ["missing", "corrupt"])
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

    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        recover(tmp_path)

    assert json.loads(journal.read_text()) == state
    assert source.exists() == (backup == "corrupt")
    with sqlite3.connect(memory) as conn:
        assert conn.execute("SELECT value FROM retained").fetchall() == [("original",)]
