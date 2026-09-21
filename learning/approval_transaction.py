"""Recover interrupted human approvals before opening learned stores.

One runtime owns a data directory. The runtime mutation lock prevents chat and
maintenance from changing learned stores while this short checkpoint is active.
Reviewer queue updates stay independent and are merged by proposal identity.
"""
from contextlib import contextmanager
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
            # Restore SQLite through its backup API, including WAL databases.
            with sqlite3.connect(root / 'data/approval_memory.sqlite') as source:
                with sqlite3.connect(root / state['memory']) as target:
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
                 'procedural_memory', 'skills', 'self_directed_learning'):
        paths.append(getattr(runtime, name).path)
    files = {}
    for path in set(paths):
        path = Path(path)
        files[str(path.relative_to(root))] = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    rows = {}
    for path in (runtime.learning_gate.path, runtime._chatgpt_review_path()):
        path = Path(path)
        rows[str(path.relative_to(root))] = [r for r in load_critical_json(path, [])
                                            if r.get('proposal_id') in proposal_ids]
    with sqlite3.connect(root / 'data/approval_memory.sqlite') as target:
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
        (root / 'data/approval_memory.sqlite').unlink(missing_ok=True)
