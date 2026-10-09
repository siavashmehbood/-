"""Recover interrupted human approvals before opening learned stores.

One runtime owns a data directory. The runtime mutation lock prevents chat and
maintenance from changing learned stores while this short checkpoint is active.
Reviewer queue updates stay independent and are merged by proposal identity.
"""
from contextlib import contextmanager, closing
from functools import wraps
from pathlib import Path
import json
import sqlite3
import threading
from persistence import atomic_write_json, file_lock, json_transaction, load_critical_json


def serialized(operation):
    @wraps(operation)
    def call(runtime, *args, **kwargs):
        with runtime.__dict__.setdefault('_mutation_lock', threading.RLock()):
            if getattr(runtime, '_closed', False):
                raise RuntimeError('Runtime is closed')
            if getattr(runtime, '_recovery_required', False):
                raise RuntimeError('Interrupted learning approval: restart required for recovery')
            return operation(runtime, *args, **kwargs)
    return call


def recover(root):
    root = Path(root)
    journal = root / 'data/approval_checkpoint.json'
    with file_lock(root / 'data/learning_apply.lock'):
        if not journal.exists():
            return
        state = load_critical_json(journal, {})
        if state.get('status') == 'prepared':
            # Validate the complete checkpoint before rolling back any store.
            # A valid SQLite snapshot cannot compensate for damaged JSON metadata.
            valid = (isinstance(state.get('memory'), str) and bool(state['memory'].strip())
                     and isinstance(state.get('files'), dict)
                     and isinstance(state.get('rows'), dict))
            if valid:
                valid = all(isinstance(name, str) and bool(name.strip())
                            for name in (*state['files'], *state['rows']))
            if valid:
                for originals in state['rows'].values():
                    if not isinstance(originals, list):
                        valid = False
                        break
                    ids = [row.get('proposal_id') if isinstance(row, dict) else None
                           for row in originals]
                    if any(not isinstance(pid, str) or not pid for pid in ids) or len(set(ids)) != len(ids):
                        valid = False
                        break
            if not valid:
                raise RuntimeError('Invalid approval recovery checkpoint; no stores were changed')
            # Restore SQLite through its backup API, including WAL databases.
            # contextlib.closing is required here: sqlite3.Connection.__exit__
            # commits/rolls back but does not close the OS file handle on Windows.
            backup_path = root / 'data/approval_memory.sqlite'
            if not backup_path.is_file():
                raise RuntimeError('Approval recovery backup is missing; refusing to overwrite memory')
            # Read-only opening must never create an empty source database.
            with closing(sqlite3.connect(backup_path.resolve().as_uri() + '?mode=ro', uri=True)) as source:
                if source.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                    raise RuntimeError('Approval recovery backup is corrupt')
                if not source.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
                    raise RuntimeError('Approval recovery backup is empty; refusing to erase memory')
                with closing(sqlite3.connect(root / state['memory'])) as target:
                    source.backup(target)
            for name, value in state['files'].items():
                path = root / name
                if value is None:
                    path.unlink(missing_ok=True)
                    path.with_suffix(path.suffix + '.bak').unlink(missing_ok=True)
                else:
                    atomic_write_json(path, value, backup=False)
                    atomic_write_json(path.with_suffix(path.suffix + '.bak'), value, backup=False)
            for name, originals in state['rows'].items():
                with json_transaction(root / name, []) as rows:
                    by_id = {r['proposal_id']: r for r in originals}
                    for i, row in enumerate(rows):
                        if row.get('proposal_id') in by_id:
                            rows[i] = by_id.pop(row['proposal_id'])
                    rows.extend(by_id.values())
        elif state.get('status') != 'committed':
            raise RuntimeError('Invalid approval recovery journal')
        journal.unlink()
        journal.with_suffix('.json.bak').unlink(missing_ok=True)
        (root / 'data/approval_memory.sqlite').unlink(missing_ok=True)


@contextmanager
def approval_checkpoint(runtime, proposal_ids):
    root = runtime.root
    journal = root / 'data/approval_checkpoint.json'
    paths = [runtime.trusted_knowledge_path, runtime.learning.rules_path,
             runtime.learning.lessons_path, runtime.skills.compositions_path]
    for name in ('knowledge', 'learning', 'effect_learning', 'outcome_learning',
                 'procedural_memory', 'skills', 'self_directed_learning', 'learning_missions'):
        paths.append(getattr(runtime, name).path)
    files = {}
    dictionary_stores = {Path(runtime.effect_learning.path), Path(runtime.self_directed_learning.path)}
    dictionary_stores.add(Path(runtime.learning_missions.path))
    for path in set(paths):
        path = Path(path)
        present = path.exists() or path.with_suffix(path.suffix + '.bak').exists()
        default = {} if path in dictionary_stores else []
        # Snapshot the same recovered value used by the live store. Reading
        # only the damaged primary would prevent any subsequent approval.
        files[str(path.relative_to(root))] = load_critical_json(path, default) if present else None
    rows = {}
    for path in (runtime.learning_gate.path, runtime._chatgpt_review_path()):
        path = Path(path)
        rows[str(path.relative_to(root))] = [r for r in load_critical_json(path, [])
                                            if r.get('proposal_id') in proposal_ids]
    with closing(sqlite3.connect(root / 'data/approval_memory.sqlite')) as target:
        runtime.memory.conn.backup(target)
    state = {'status': 'prepared', 'memory': runtime.config['memory']['db'],
             'files': files, 'rows': rows}
    atomic_write_json(journal, state, backup=False)
    try:
        yield
        state['status'] = 'committed'
        atomic_write_json(journal, state, backup=False)
    except BaseException:
        runtime._recovery_required = True
        raise
    else:
        journal.unlink()
        journal.with_suffix('.json.bak').unlink(missing_ok=True)
        (root / 'data/approval_memory.sqlite').unlink(missing_ok=True)
