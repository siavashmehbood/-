from collections import Counter, deque
from dataclasses import dataclass
from collections import Counter, deque
import math


@dataclass
class Anomaly:
    value: str
    score: float
    reason: str


class AnomalyDetector:
    """Adaptive local baseline detector for rare patterns and sudden frequency shifts."""
    def __init__(self, window=200):
        self.counts = Counter()
        self.total = 0
        self.recent = deque(maxlen=window)
        self.window = window

    def observe(self, value):
        key = str(value)
        self.total += 1
        self.counts[key] += 1
        self.recent.append(key)
        global_p = self.counts[key] / self.total
        local_p = self.recent.count(key) / max(1, len(self.recent))
        score = max(0.0, min(1.0, 1 - math.sqrt(max(global_p * .6 + local_p * .4, 1e-9))))
        reason = 'rare or shifted from baseline' if score >= .5 else 'within observed baseline'
        return Anomaly(key, round(score, 3), reason)

    def compare(self, value):
        key = str(value)
        return {
            'value': key,
            'global_frequency': self.counts[key] / max(1, self.total),
            'recent_frequency': self.recent.count(key) / max(1, len(self.recent)),
        }

    def baseline(self):
        return {
            'observations': self.total,
            'patterns': len(self.counts),
            'common': self.counts.most_common(10),
        }
