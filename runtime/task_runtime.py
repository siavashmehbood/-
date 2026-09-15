from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any
from persistence import atomic_write_json, load_json_with_backup


class TaskStatus(str, Enum):
    CREATED = 'created'
    READY = 'ready'
    RUNNING = 'running'
    WAITING = 'waiting'
    BLOCKED = 'blocked'
    SUCCESS = 'success'
    FAILED = 'failed'
    REPLANNING = 'replanning'
    CANCELLED = 'cancelled'


@dataclass
class Task:
    task_id: str
    goal_id: str | None
    description: str
    status: TaskStatus = TaskStatus.CREATED
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    attempts: int = 0
    expected_result: str = ''
    actual_result: str = ''
    verification: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, status: TaskStatus, reason: str = ''):
        previous = self.status.value
        self.status = status
        self.history.append({'at': datetime.now().isoformat(timespec='seconds'),
                             'from': previous, 'to': status.value, 'reason': reason})

    def start(self):
        self.attempts += 1
        self.transition(TaskStatus.RUNNING, 'execution started')

    def verify(self, actual_result: str, evidence: Any = None, success: bool = False):
        self.actual_result = actual_result
        self.verification = {'success': bool(success), 'evidence': evidence,
                             'verified_at': datetime.now().isoformat(timespec='seconds')}
        self.transition(TaskStatus.SUCCESS if success else TaskStatus.FAILED,
                        'verification result')
        return self.verification

    def replan(self, reason: str):
        self.transition(TaskStatus.REPLANNING, reason)


class TaskRuntime:
    """Persistent task state machine; execution is deliberately delegated to callers."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save([])

    def _save(self, tasks):
        atomic_write_json(self.path, tasks)

    def _load(self):
        return load_json_with_backup(self.path, [])

    def create(self, description, goal_id=None, task_id=None, **kwargs):
        task_id = task_id or f"task-{int(datetime.now().timestamp() * 1000)}"
        task = Task(task_id, goal_id, description, **kwargs)
        items = self._load()
        items.append(asdict(task) | {'status': task.status.value})
        self._save(items)
        return task

    def get(self, task_id):
        for item in self._load():
            if item.get('task_id') == task_id:
                return item
        return None

    def transition(self, task_id, status, reason=''):
        items = self._load()
        for item in items:
            if item.get('task_id') == task_id:
                previous = item.get('status')
                item['status'] = TaskStatus(status).value
                item.setdefault('history', []).append({
                    'at': datetime.now().isoformat(timespec='seconds'),
                    'from': previous, 'to': item['status'], 'reason': reason})
                if item['status'] == TaskStatus.RUNNING.value:
                    item['attempts'] = int(item.get('attempts', 0)) + 1
                self._save(items)
                return item
        return None


# v0.25: explicit lifecycle guard prevents impossible state jumps.
_ALLOWED_TRANSITIONS = {
    TaskStatus.CREATED: {TaskStatus.READY, TaskStatus.CANCELLED if hasattr(TaskStatus, 'CANCELLED') else TaskStatus.FAILED},
    TaskStatus.READY: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.CANCELLED if hasattr(TaskStatus, 'CANCELLED') else TaskStatus.FAILED},
    TaskStatus.RUNNING: {TaskStatus.WAITING, TaskStatus.BLOCKED, TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.REPLANNING},
    TaskStatus.WAITING: {TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.REPLANNING},
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.REPLANNING},
    TaskStatus.FAILED: {TaskStatus.REPLANNING, TaskStatus.READY},
    TaskStatus.REPLANNING: {TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.FAILED},
    TaskStatus.SUCCESS: set(),
}
_old_transition = TaskRuntime.transition

def _guarded_transition(self, task_id, status, reason=''):
    target = TaskStatus(status)
    current = self.get(task_id)
    if current is None:
        return None
    source = TaskStatus(current.get('status', TaskStatus.CREATED.value))
    allowed = _ALLOWED_TRANSITIONS.get(source, set())
    if target not in allowed and target != source:
        raise ValueError(f'invalid task transition: {source.value} -> {target.value}')
    return _old_transition(self, task_id, target.value, reason)

TaskRuntime.transition = _guarded_transition
