"""Lightweight causal graph for explicit local reasoning."""
from dataclasses import dataclass, field

@dataclass
class CausalGraph:
    edges: dict[str, set[str]] = field(default_factory=dict)

    def add(self, cause, effect):
        cause, effect = str(cause).strip(), str(effect).strip()
        if cause and effect:
            self.edges.setdefault(cause, set()).add(effect)

    def effects(self, cause, max_depth=3):
        seen, frontier, result = {cause}, [cause], []
        for _ in range(max_depth):
            nxt = []
            for node in frontier:
                for effect in self.edges.get(node, set()):
                    if effect not in seen:
                        seen.add(effect); result.append(effect); nxt.append(effect)
            frontier = nxt
            if not frontier: break
        return result

    def causes(self, effect):
        return [cause for cause, targets in self.edges.items() if effect in targets]

    def path(self, source, target, max_depth=5):
        queue = [(source, [source])]; seen = {source}
        while queue:
            node, path = queue.pop(0)
            if node == target: return path
            if len(path) > max_depth: continue
            for nxt in self.edges.get(node, set()):
                if nxt not in seen:
                    seen.add(nxt); queue.append((nxt, path + [nxt]))
        return []

    def snapshot(self):
        return {k: sorted(v) for k, v in self.edges.items()}
