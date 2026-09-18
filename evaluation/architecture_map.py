"""Static architecture map for IRAN.

Answers three questions the test suite cannot:

1. which modules are actually reachable from the real entry points
   (orphaned code is code that is tested but never used);
2. which class names are defined more than once (parallel cores);
3. how the modules line up against the target architecture.
"""
from __future__ import annotations

import ast
import collections
import json
import sys
from pathlib import Path

ENTRY_POINTS = ["runtime.app", "gui", "main", "run_autonomy"]
SKIP_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "sandbox",
    "data",
    "logs",
    "docs",
    "tests",
}


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    name = ".".join(rel.parts)
    if name.endswith(".__init__"):
        name = name[: -len(".__init__")]
    return name


def collect(root: Path) -> dict[str, Path]:
    mods: dict[str, Path] = {}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        mods[_module_name(path, root)] = path
    return mods


def imports_of(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
    return out


def build_graph(mods: dict[str, Path]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for name, path in mods.items():
        graph[name] = {dep for dep in imports_of(path) if dep in mods}
    return graph


def reachable(graph: dict[str, set[str]], starts: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = [s for s in starts if s in graph]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(dep for dep in graph.get(node, ()) if dep not in seen)
    return seen


def duplicate_classes(mods: dict[str, Path]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = collections.defaultdict(list)
    for name, path in mods.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                owners[node.name].append(name)
    return {k: sorted(v) for k, v in owners.items() if len(v) > 1}


def unparseable(mods: dict[str, Path]) -> list[str]:
    bad = []
    for name, path in mods.items():
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            bad.append(f"{name}: UTF-8 BOM at start of file")
        try:
            ast.parse(raw.decode("utf-8-sig"))
        except SyntaxError as exc:
            bad.append(f"{name}: {exc}")
    return bad


def analyse(root: Path | str | None = None) -> dict:
    root = Path(root or Path(__file__).resolve().parents[1])
    mods = collect(root)
    graph = build_graph(mods)
    live = reachable(graph, ENTRY_POINTS)
    orphans = sorted(set(mods) - live - {"evaluation", "evaluation.maturity", "evaluation.architecture_map"})
    orphans = [o for o in orphans if not o.startswith("evaluation")]
    lines = {name: len(path.read_text(encoding="utf-8-sig").splitlines()) for name, path in mods.items()}
    return {
        "total_modules": len(mods),
        "live_modules": len(live),
        "orphan_modules": orphans,
        "orphan_lines": sum(lines[o] for o in orphans),
        "total_lines": sum(lines.values()),
        "duplicate_classes": duplicate_classes(mods),
        "unparseable": unparseable(mods),
        "largest": sorted(lines.items(), key=lambda kv: -kv[1])[:8],
    }


def render(report: dict) -> str:
    out = []
    dead_pct = 100.0 * report["orphan_lines"] / max(report["total_lines"], 1)
    out.append(
        f"modules: {report['live_modules']}/{report['total_modules']} reachable from entry points"
    )
    out.append(
        f"orphaned code: {report['orphan_lines']}/{report['total_lines']} lines ({dead_pct:.1f}%)"
    )
    if report["orphan_modules"]:
        out.append("\nORPHANED MODULES (exist and are tested, but nothing runs them):")
        for name in report["orphan_modules"]:
            out.append(f"  - {name}")
    if report["duplicate_classes"]:
        out.append("\nDUPLICATE CLASS NAMES (parallel cores):")
        for cls, owners in sorted(report["duplicate_classes"].items()):
            out.append(f"  - {cls}: {', '.join(owners)}")
    if report["unparseable"]:
        out.append("\nBROKEN SOURCE FILES:")
        for item in report["unparseable"]:
            out.append(f"  - {item}")
    out.append("\nLARGEST MODULES:")
    for name, count in report["largest"]:
        out.append(f"  {count:6d}  {name}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    report = analyse()
    print(render(report))
    if "--json" in argv:
        path = Path(__file__).resolve().parents[1] / "data" / "architecture_map.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
