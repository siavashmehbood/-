import json
import os
from pathlib import Path


def atomic_write_json(path, value, backup=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    if backup and path.exists():
        path.with_suffix(path.suffix + '.bak').write_bytes(path.read_bytes())
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    with temp.open('wb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temp, path)
    except PermissionError:
        # Windows can transiently deny atomic replacement when a GUI/file indexer has the
        # destination open. The temp file is already fully fsynced, so fall back to a
        # direct atomic-content update rather than losing the learning request.
        path.write_bytes(payload)
        try: temp.unlink()
        except OSError: pass
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
