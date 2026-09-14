from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable
import uuid


@dataclass
class ActionContract:
    action_id: str
    task_id: str
    name: str
    expected_effect: str
    preconditions: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    actual_effect: str = ''
    result: Any = None
    evidence: list[Any] = field(default_factory=list)
    side_effects: list[Any] = field(default_factory=list)
    success: bool = False


class ActionExecutor:
    """Permission-gated action execution; never treats return value as proof."""
    def __init__(self, registry, policy, events):
        self.registry, self.policy, self.events = registry, policy, events

    def execute(self, task_id: str, name: str, expected_effect: str, **kwargs):
        tool = self.registry.get(name)
        if tool is None:
            raise KeyError(f'unknown tool: {name}')
        if self.policy and not self.policy.allows(tool.permission):
            raise PermissionError(f'permission denied: {tool.permission}')
        action = ActionContract(
            action_id=f'action-{uuid.uuid4().hex[:12]}', task_id=task_id,
            name=name, expected_effect=expected_effect,
            permissions=[tool.permission], started_at=datetime.now().isoformat(timespec='seconds'))
        self.events.emit('action_started', asdict(action))
        try:
            action.result = self.registry.run(name, **kwargs)
            action.completed_at = datetime.now().isoformat(timespec='seconds')
            self.events.emit('action_completed', asdict(action))
        except Exception as exc:
            action.completed_at = datetime.now().isoformat(timespec='seconds')
            action.result = {'error': type(exc).__name__, 'message': str(exc)}
            self.events.emit('action_failed', asdict(action))
            raise
        return action
