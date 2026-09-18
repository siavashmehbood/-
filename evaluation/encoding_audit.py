"""Repository-wide encoding audit: BOM, mojibake, and undecodable Persian text."""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP = {".git", "__pycache__", ".pytest_cache", "sandbox", "logs"}
# Mojibake signature: UTF-8 Persian bytes mis-decoded as Windows-1252/Latin-1
# then re-encoded as UTF-8. These byte sequences do not occur in clean
# Persian or English source.
MOJIBAKE_RE = re.compile(r"[ÃÂØÙÚ][\x80-\xbf]")


def scan(root: Path) -> dict:
    bom_files, mojibake_files, bad_files = [], [], []
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        raw = path.read_bytes()
        rel = str(path.relative_to(root))
        if raw.startswith(b"\xef\xbb\xbf"):
            bom_files.append(rel)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            bad_files.append(f"{rel}: {exc}")
            continue
        if MOJIBAKE_RE.search(text):
            mojibake_files.append(rel)
    return {"bom": bom_files, "mojibake": mojibake_files, "undecodable": bad_files}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = scan(root)
    print(f"BOM files: {len(report['bom'])}")
    for f in report["bom"]:
        print("  -", f)
    print(f"Mojibake files: {len(report['mojibake'])}")
    for f in report["mojibake"]:
        print("  -", f)
    print(f"Undecodable files: {len(report['undecodable'])}")
    for f in report["undecodable"]:
        print("  -", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
