"""Local, self-verifying programming practice loop for IRAN.

This is the first programming-learning layer. It does not call an LLM or
external service. IRAN receives a small curriculum, produces a candidate
program from known construction rules, runs it in a temporary subprocess,
checks the output against an independent oracle, records the evidence, and
uses verified outcomes to choose the next exercise.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import ast
import json
import subprocess
import sys
import tempfile
import time
from typing import Callable


@dataclass(frozen=True)
class ProgrammingLesson:
    lesson_id: str
    level: int
    title: str
    task: str
    expected: str
    concepts: tuple[str, ...]


@dataclass
class ProgrammingAttempt:
    lesson_id: str
    code: str
    stdout: str
    stderr: str
    returncode: int
    passed: bool
    score: float
    elapsed_ms: int
    reason: str


class CodeSafetyError(ValueError):
    pass


class LocalCodeSandbox:
    """Execute one Python candidate in a disposable local directory."""

    ALLOWED_MODULES = {"math", "json", "re", "statistics"}
    BLOCKED_CALLS = {"eval", "exec", "compile", "__import__", "input"}
    BLOCKED_NODES = (ast.ImportFrom,)

    def validate(self, code: str) -> None:
        tree = ast.parse(code, mode="exec")
        for node in ast.walk(tree):
            if isinstance(node, self.BLOCKED_NODES):
                raise CodeSafetyError("from-import is not allowed in the learning sandbox")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] not in self.ALLOWED_MODULES:
                        raise CodeSafetyError(f"module not allowed: {alias.name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in self.BLOCKED_CALLS:
                    raise CodeSafetyError(f"call not allowed: {node.func.id}")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise CodeSafetyError("dunder attribute is not allowed")

    def run(self, code: str, timeout: float = 2.0) -> tuple[str, str, int, int]:
        self.validate(code)
        with tempfile.TemporaryDirectory(prefix="iran_code_") as td:
            path = Path(td) / "main.py"
            path.write_text(code, encoding="utf-8")
            started = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, "-I", str(path)],
                cwd=td,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PYTHONIOENCODING": "utf-8"},
            )
            elapsed = int((time.perf_counter() - started) * 1000)
            return proc.stdout.strip(), proc.stderr.strip(), proc.returncode, elapsed


class ProgrammingCurriculum:
    """Ordered beginner curriculum with independent output oracles."""

    def __init__(self):
        self.lessons = [
            ProgrammingLesson("py01", 1, "print", "Print exactly HELLO IRAN", "HELLO IRAN", ("print",)),
            ProgrammingLesson("py02", 2, "variables", "Create x=7 and print x+5", "12", ("variables", "arithmetic")),
            ProgrammingLesson("py03", 3, "condition", "Print BIG when x=10 is greater than 5", "BIG", ("if", "comparison")),
            ProgrammingLesson("py04", 4, "loop", "Print 1, 2, 3 on separate lines", "1" + chr(10) + "2" + chr(10) + "3", ("for", "range")),
            ProgrammingLesson("py05", 5, "function", "Define add(a,b) and print add(4,6)", "10", ("function", "return")),
            ProgrammingLesson("py06", 6, "list", "Print the sum of [2,3,5]", "10", ("list", "sum")),
            ProgrammingLesson("py07", 7, "dictionary", "Print the value of name from {'name':'IRAN'}", "IRAN", ("dict", "lookup")),
        ]

    def get(self, lesson_id: str) -> ProgrammingLesson:
        return next(x for x in self.lessons if x.lesson_id == lesson_id)


class ProgrammingLearner:
    """Learn programming basics through generate -> execute -> verify -> learn."""

    def __init__(self, data_dir: str | Path, outcome_learning=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.data_dir / "programming_learning.json"
        self.curriculum = ProgrammingCurriculum()
        self.sandbox = LocalCodeSandbox()
        self.outcome_learning = outcome_learning
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"completed": [], "attempts": [], "mastery": {}, "last_lesson": None}

    def _save(self):
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def next_lesson(self) -> ProgrammingLesson | None:
        completed = set(self.state.get("completed", []))
        for lesson in self.curriculum.lessons:
            if lesson.lesson_id not in completed:
                return lesson
        return None

    def generate_candidate(self, lesson: ProgrammingLesson) -> str:
        """Small deterministic code synthesizer; this is intentionally transparent."""
        candidates = {
            "py01": 'print("HELLO IRAN")',
            "py02": 'x = 7\nprint(x + 5)',
            "py03": 'x = 10\nif x > 5:\n    print("BIG")',
            "py04": 'for i in range(1, 4):\n    print(i)',
            "py05": 'def add(a, b):\n    return a + b\n\nprint(add(4, 6))',
            "py06": 'numbers = [2, 3, 5]\nprint(sum(numbers))',
            "py07": 'person = {"name": "IRAN"}\nprint(person["name"])',
        }
        return candidates[lesson.lesson_id]

    def attempt(self, lesson: ProgrammingLesson, code: str | None = None) -> ProgrammingAttempt:
        code = code if code is not None else self.generate_candidate(lesson)
        try:
            stdout, stderr, returncode, elapsed = self.sandbox.run(code)
            passed = returncode == 0 and stdout == lesson.expected
            reason = "verified output matches oracle" if passed else "output/error mismatch"
            score = 1.0 if passed else 0.0
        except Exception as exc:
            stdout, stderr, returncode, elapsed = "", str(exc), -1, 0
            passed, score, reason = False, 0.0, f"sandbox rejected execution: {type(exc).__name__}"

        result = ProgrammingAttempt(lesson.lesson_id, code, stdout, stderr, returncode, passed, score, elapsed, reason)
        self.state.setdefault("attempts", []).append(asdict(result))
        self.state["attempts"] = self.state["attempts"][-1000:]
        self.state["last_lesson"] = lesson.lesson_id
        if passed:
            completed = set(self.state.setdefault("completed", []))
            completed.add(lesson.lesson_id)
            self.state["completed"] = [x.lesson_id for x in self.curriculum.lessons if x.lesson_id in completed]
            self.state.setdefault("mastery", {})[lesson.lesson_id] = 1.0
        self._save()

        if self.outcome_learning is not None:
            self.outcome_learning.record_outcome(
                goal=f"learn Python {lesson.lesson_id}: {lesson.title}",
                action="generate_execute_verify",
                result=json.dumps(asdict(result), ensure_ascii=False),
                expected=lesson.expected,
                verification={"verified": passed, "source": "local_python_oracle", "score": score},
                strategy="generate_execute_verify",
                domain="programming",
                episode_id=f"programming:{lesson.lesson_id}",
                phase="practice",
                attempt=len(self.state["attempts"]),
            )
        return result

    def practice(self, cycles: int = 1) -> list[dict]:
        report = []
        for _ in range(max(1, cycles)):
            lesson = self.next_lesson()
            if lesson is None:
                break
            attempt = self.attempt(lesson)
            report.append({"lesson": asdict(lesson), "attempt": asdict(attempt)})
            if not attempt.passed:
                break
        return report

    def status(self) -> dict:
        return {
            "completed": len(self.state.get("completed", [])),
            "total": len(self.curriculum.lessons),
            "mastery": self.state.get("mastery", {}),
            "next": self.next_lesson().lesson_id if self.next_lesson() else None,
            "attempts": len(self.state.get("attempts", [])),
        }



