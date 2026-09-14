import time
from collections import defaultdict

class Metrics:
    def __init__(self):
        self.started = time.time()
        self.counts = defaultdict(int)
        self.latencies = []

    def record(self, event, elapsed=0):
        self.counts[str(event)] += 1
        if elapsed: self.latencies.append(float(elapsed))

    def snapshot(self):
        avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        return {'uptime_s': round(time.time()-self.started, 2), 'events': dict(self.counts), 'avg_latency_ms': round(avg*1000, 2), 'samples': len(self.latencies)}
