"""Deterministic production-system layer for IRAN.

Rules operate on symbolic facts and return transparent actions. No model or
external service is involved; matching and conflict resolution are inspectable.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductionRule:
    name: str
    conditions: tuple[str, ...]
    action: str
    priority: int = 0
    confidence: float = 1.0


@dataclass
class RuleMatch:
    rule: ProductionRule
    bindings: dict[str, str] = field(default_factory=dict)


class ProductionSystem:
    """Forward-chaining symbolic production system with deterministic firing."""

    def __init__(self, rules=None):
        self.rules = list(rules or [])

    def add(self, name, conditions, action, priority=0, confidence=1.0):
        if isinstance(conditions, str):
            conditions = (conditions,)
        rule = ProductionRule(str(name), tuple(map(str, conditions)), str(action),
                              int(priority), float(confidence))
        if rule not in self.rules:
            self.rules.append(rule)
        return rule

    @staticmethod
    def _match(condition, facts):
        """Match exact facts or a single ``{slot}`` placeholder."""
        condition = str(condition)
        if condition in facts:
            return {}
        if "{" not in condition or "}" not in condition:
            return None
        prefix, rest = condition.split("{", 1)
        slot, suffix = rest.split("}", 1)
        for fact in facts:
            fact = str(fact)
            if fact.startswith(prefix) and fact.endswith(suffix):
                value = fact[len(prefix):len(fact) - len(suffix) if suffix else None]
                if value:
                    return {slot: value}
        return None

    def match(self, facts):
        fact_set = {str(f) for f in facts}
        matches = []
        for rule in self.rules:
            bindings = {}
            ok = True
            for condition in rule.conditions:
                found = self._match(condition, fact_set)
                if found is None:
                    ok = False
                    break
                bindings.update(found)
            if ok:
                matches.append(RuleMatch(rule, bindings))
        return sorted(matches, key=lambda m: (-m.rule.priority, -m.rule.confidence, m.rule.name))

    def fire(self, facts, limit=1):
        fired = []
        for match in self.match(facts)[:max(0, int(limit))]:
            action = match.rule.action
            for key, value in match.bindings.items():
                action = action.replace("{" + key + "}", value)
            fired.append({"rule": match.rule.name, "action": action,
                          "confidence": match.rule.confidence,
                          "priority": match.rule.priority,
                          "bindings": dict(match.bindings)})
        return fired

    def snapshot(self):
        return [rule.__dict__.copy() for rule in self.rules]
