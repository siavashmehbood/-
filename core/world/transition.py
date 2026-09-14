from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

@dataclass
class StateTransition:
    transition_id: str
    task_id: str
    action_id: str
    state_before: dict
    action: dict
    observation: dict
    verification: dict
    state_after: dict
    timestamp: str

class TransitionRecorder:
    """Records evidence-backed state transitions independently of response score."""
    def __init__(self, world_model):
        self.world = world_model

    def record(self, task_id, action, observation, verification, state_before=None):
        before = dict(state_before or {})
        after = dict(before)
        after.update({
            'last_action': action.get('tool_name'),
            'last_verified': bool(verification.get('success')),
            'last_observation': observation.get('summary', ''),
        })
        transition = StateTransition(
            transition_id=f'trans-{uuid.uuid4().hex[:12]}',
            task_id=task_id,
            action_id=action.get('action_id', ''),
            state_before=before,
            action=dict(action),
            observation=dict(observation),
            verification=dict(verification),
            state_after=after,
            timestamp=datetime.now().isoformat(timespec='seconds'),
        )
        if hasattr(self.world, 'observe'):
            self.world.observe({'type': 'verified_transition', **asdict(transition)})
        return transition
