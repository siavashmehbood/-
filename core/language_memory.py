from dataclasses import dataclass, field
from collections import deque
import re

@dataclass
class DiscourseState:
    turns: int = 0
    last_intent: str = 'general'
    last_goal: str = ''
    last_entities: list[str] = field(default_factory=list)
    last_topic: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    recent: deque = field(default_factory=lambda: deque(maxlen=12))

class DiscourseMemory:
    """Small local discourse memory used by the language brain."""
    def __init__(self, max_turns=12):
        self.state=DiscourseState(recent=deque(maxlen=max_turns))

    def update(self, analysis):
        s=self.state; s.turns+=1
        s.last_intent=analysis.intent; s.last_goal=analysis.goal
        s.last_entities=list(analysis.entities); s.last_topic=list(analysis.entities[:8])
        s.recent.append({'intent':analysis.intent,'goal':analysis.goal,
                         'entities':list(analysis.entities),'text':analysis.normalized})

    def resolve(self, text, analysis):
        """Resolve simple Persian references using the latest discourse state."""
        if not self.state.recent: return analysis
        refs=('این','اون','آن','همین','همون','آنها','اونا','قبلی','همان','همون فایل','همون خطا')
        if not any(r in text for r in refs): return analysis
        if self.state.last_entities:
            analysis.entities=list(dict.fromkeys(analysis.entities+self.state.last_entities))[:40]
        if not analysis.goal and self.state.last_goal:
            analysis.goal=self.state.last_goal
        return analysis

    def context(self):
        return list(self.state.recent)
