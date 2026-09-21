import json
import os
from pathlib import Path


def atomic_write_json(path, value, backup=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import uuid
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    if backup and path.exists():
        previous = path.read_bytes()
        try:
            json.loads(previous)
        except (ValueError, UnicodeError):
            pass  # Preserve the last valid backup when recovering a damaged primary.
        else:
            path.with_suffix(path.suffix + '.bak').write_bytes(previous)
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
        value = load_critical_json(path, default)
        before = json.dumps(value, sort_keys=True)
        yield value
        if json.dumps(value, sort_keys=True) != before or not path.exists():
            atomic_write_json(path, value)


class StateCorruptionError(RuntimeError):
    """Existing durable state cannot be read; never silently reset it."""

def load_critical_json(path, default):
    path = Path(path)
    present = False
    for candidate in (path, path.with_suffix(path.suffix + '.bak')):
        if not candidate.exists():
            continue
        present = True
        try:
            value = json.loads(candidate.read_text(encoding='utf-8'))
            if not isinstance(value, type(default)):
                continue
            return value
        except (OSError, ValueError, UnicodeError):
            continue
    if present:
        raise StateCorruptionError('Unreadable durable state: ' + str(path))
    return default


class RuntimeAlreadyRunning(RuntimeError):
    """Another runtime owns the learned stores in this data directory."""


def acquire_runtime_ownership(path):
    """Hold a nonblocking OS lock until the returned handle is closed.

    The file remains on disk; process termination releases its lock, so stale
    PID files cannot strand a queue. This is separate from short queue locks.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    try:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeAlreadyRunning('Data directory is already owned or cannot be locked: ' + str(path.parent)) from exc
    return handle
