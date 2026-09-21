import json
import os
from pathlib import Path


def atomic_write_json(path, value, backup=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import uuid
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    if backup and path.exists():
        path.with_suffix(path.suffix + '.bak').write_bytes(path.read_bytes())
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    with temp.open('wb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    try:
        directory = os.open(str(path.parent), os.O_RDONLY)
        os.fsync(directory)
        os.close(directory)
    except OSError:
        pass


def load_json_with_backup(path, default):
    path = Path(path)
    for candidate in (path, path.with_suffix(path.suffix + '.bak')):
        if not candidate.exists():
            continue
        try:
            return json.loads(candidate.read_text(encoding='utf-8'))
        except (OSError, ValueError, TypeError):
            continue
    return default


# Short cross-thread/process transactions; never hold a queue lock over network I/O.
from contextlib import contextmanager
import threading
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()

@contextmanager
def file_lock(path):
    path = Path(path).resolve()
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(str(path), threading.RLock())
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

@contextmanager
def json_transaction(path, default):
    path = Path(path)
    with file_lock(path.with_suffix(path.suffix + '.lock')):
        value = load_json_with_backup(path, default)
        before = json.dumps(value, sort_keys=True)
        yield value
        if json.dumps(value, sort_keys=True) != before or not path.exists():
            atomic_write_json(path, value)
