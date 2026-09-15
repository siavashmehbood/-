import json
import uuid
from datetime import datetime
from pathlib import Path

class EventLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.current_turn_id = None

    def begin_turn(self, turn_id=None):
        self.current_turn_id = str(turn_id or uuid.uuid4())
        return self.current_turn_id

    @staticmethod
    def _stage(event):
        if event in {'language_analysis', 'user_model_update'}: return 'perception'
        if event in {'cognitive_cycle', 'memory_retrieval', 'knowledge_retrieval', 'reasoning_completed', 'prediction_completed'}: return 'cognition'
        if event in {'goal_identified', 'plan_created', 'task_plan_created', 'decision_made'}: return 'planning'
        if event in {'action_started', 'action_observed', 'verification_completed', 'verified_task_completed'}: return 'action'
        if event in {'evaluation_completed', 'reflection', 'learning_update', 'strategy_reused'}: return 'learning'
        if event in {'response_generated'}: return 'response'
        return 'runtime'

    def emit(self, event, data=None):
        payload = dict(data or {})
        record = {
            'time': datetime.now().isoformat(timespec='seconds'),
            'event': event,
            'turn_id': payload.pop('turn_id', None) or self.current_turn_id or 'system',
            'stage': payload.pop('stage', None) or self._stage(event),
            'status': payload.pop('status', None) or 'completed',
            'duration_ms': payload.pop('duration_ms', 0.0),
            'data': payload,
        }
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        return record

    def recent(self, limit=20):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding='utf-8').splitlines()
        return [json.loads(x) for x in lines[-limit:]]
