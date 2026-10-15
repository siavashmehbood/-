"""Start only an explicitly configured local model with the desktop application."""
from pathlib import Path
import json
import socket
import subprocess
from urllib.parse import urlparse


def start_local_server(root):
    root = Path(root)
    settings = root / "language.local.json"
    if not settings.exists():
        return None
    cfg = json.loads(settings.read_text(encoding="utf-8-sig"))
    if not isinstance(cfg, dict) or not cfg.get("enabled"):
        return None
    runtime = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    language = runtime.get("language_engine", {})
    if not language.get("enabled"):
        return None
    url = urlparse(language.get("endpoint", ""))
    # Explicit numeric loopback only: never publish a model server to the LAN.
    if url.scheme != "http" or url.hostname != "127.0.0.1" or not url.port:
        raise ValueError("managed language server requires http://127.0.0.1:<port>")
    exe = Path(cfg.get("executable", ""))
    model = Path(cfg.get("model_path", ""))
    if not exe.is_file() or not model.is_file():
        raise FileNotFoundError("local language executable or model is missing")
    try:
        with socket.create_connection(("127.0.0.1", url.port), timeout=.2):
            return None  # Never own or stop a server started by someone else.
    except OSError:
        pass
    log_dir = root / "logs"
    log_dir.mkdir(exist_ok=True)
    with (log_dir / "local_language_server.log").open("ab") as log:
        return subprocess.Popen(
            [str(exe), "-m", str(model), "--alias", str(language["model"]),
             "--host", "127.0.0.1", "--port", str(url.port),
             "-c", "2048", "-t", "2", "-b", "128", "-ub", "128",
             "--parallel", "1", "--reasoning", "off", "--no-webui"],
            cwd=str(exe.parent), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
