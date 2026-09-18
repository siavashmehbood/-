"""Durable local memory consolidation and forgetting coordinator."""
from __future__ import annotations

class MemoryConsolidator:
    def __init__(self, memory, learning=None):
        self.memory = memory
        self.learning = learning

    def run(self, limit=20, decay_days=120):
        semantic = getattr(self.memory, "semantic", None)
        consolidated = semantic.consolidate(limit) if semantic and hasattr(semantic, "consolidate") else {}
        if self.learning is not None and hasattr(self.learning, "auto_maintenance"):
            learning_maintenance = self.learning.auto_maintenance()
        else:
            learning_maintenance = {}
        decayed = self.memory.decay(decay_days) if hasattr(self.memory, "decay") else {}
        return {"consolidated": consolidated, "learning": learning_maintenance, "decayed": decayed}

    def consolidate(self, limit=20):
        return self.run(limit=limit, decay_days=120)["consolidated"]

    def forget(self, days=120):
        return self.memory.decay(days) if hasattr(self.memory, "decay") else {"decayed": 0}
