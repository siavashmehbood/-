"""Transparent symbolic analogy and structure matching."""
from dataclasses import dataclass

@dataclass
class AnalogyResult:
    source: str
    target: str
    score: float
    shared: list[str]
    missing: list[str]

class AnalogicalReasoner:
    @staticmethod
    def _parts(value):
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        text = str(value)
        parts = [p.strip() for p in text.replace("→", "->").split("->") if p.strip()]
        return {str(i): p for i, p in enumerate(parts)}

    def compare(self, source, target):
        a, b = self._parts(source), self._parts(target)
        shared = [k for k in a if k in b and a[k] == b[k]]
        missing = [k for k in a if k not in b or a[k] != b[k]]
        score = len(shared) / max(1, len(set(a) | set(b)))
        return AnalogyResult(str(source), str(target), round(score, 3), shared, missing)

    def infer(self, source, target, mapping):
        src, dst = self._parts(source), self._parts(target)
        out = dict(dst)
        for src_key, dst_key in mapping.items():
            if src_key in src and dst_key not in out:
                out[dst_key] = src[src_key]
        return out
