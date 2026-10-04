"""Feasibility gate applied after quality hard gates, never mixed into correctness."""
from __future__ import annotations


class DeploymentGate:
    def __init__(self, max_ram_mb=None, max_vram_mb=None, min_tokens_per_second=None):
        self.max_ram_mb=max_ram_mb
        self.max_vram_mb=max_vram_mb
        self.min_tokens_per_second=min_tokens_per_second

    def evaluate(self, metrics):
        reasons=[]
        if self.max_ram_mb is not None and metrics.peak_ram_mb > self.max_ram_mb:
            reasons.append("ram_budget_exceeded")
        if self.max_vram_mb is not None and metrics.peak_vram_mb > self.max_vram_mb:
            reasons.append("vram_budget_exceeded")
        if self.min_tokens_per_second is not None and metrics.tokens_per_second < self.min_tokens_per_second:
            reasons.append("throughput_below_minimum")
        return {"passed":not reasons,"reasons":reasons,"metrics":metrics.to_dict()}
