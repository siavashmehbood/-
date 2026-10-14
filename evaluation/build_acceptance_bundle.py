"""Archive only tracked source; no personal data, logs, credentials or model weights."""
import io
import json
import subprocess
import zipfile
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[1]
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    config = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    archive = subprocess.check_output(["git", "archive", "--format=zip", "HEAD"], cwd=root)
    target = root / "dist" / f"IRAN-{config['version']}-{sha[:12]}.zip"
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as output:
        for entry in source.infolist():
            path = entry.filename
            if (path.startswith(("data/", "logs/", ".venv/")) or
                    path.endswith((".gguf", ".onnx", ".db", ".sqlite", ".sqlite3")) or
                    path in {"reviewers.local.json", ".env", "gui_startup.log"}):
                raise RuntimeError("Sensitive/unexpected tracked bundle entry: " + path)
            output.writestr(path, source.read(path))
        manifest = {
            "version":config["version"], "commit":sha, "python":"3.12",
            "data_path":config["memory"]["db"], "runtime_paths":config["runtime"],
            "requirements":["requirements.txt","requirements-dev.txt","requirements-jarvis.txt"],
            "instructions":"docs/FINAL_ACCEPTANCE.md",
            "external_models_included":False,
            "device_acceptance":"NOT_RUN",
            "live_reviewer":"BLOCKED_EXTERNAL unless separately evidenced",
            "gates":"All three required Actions successful on this exact commit"
        }
        output.writestr("RELEASE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(target) as check:
        if check.testzip() is not None:
            raise RuntimeError("Bundle integrity failure")
        if json.loads(check.read("RELEASE_MANIFEST.json"))["commit"] != sha:
            raise RuntimeError("Bundle commit mismatch")
    print(target)

if __name__ == "__main__":
    main()
