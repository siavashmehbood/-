from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    antecedent: str
    consequent: str
    confidence: float = .8
    source: str = 'local'


@dataclass
class RuleInference:
    conclusion: str
    confidence: float
    chain: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


class SymbolicRuleEngine:
    """Small explainable forward-chaining engine; it never executes code."""

    def __init__(self, rules=None):
        self.rules = list(rules or [])

    def add(self, antecedent, consequent, confidence=.8, source='local'):
        rule = Rule(str(antecedent), str(consequent), float(confidence), str(source))
        if rule not in self.rules:
            self.rules.append(rule)
        return rule

    def infer(self, facts, target=None, max_hops=5):
        known = {str(f) for f in facts}
        confidence = {str(f): 1.0 for f in facts}
        chain = []
        for _ in range(int(max_hops)):
            changed = False
            for rule in self.rules:
                if rule.antecedent in known and rule.consequent not in known:
                    known.add(rule.consequent)
                    confidence[rule.consequent] = round(confidence[rule.antecedent] * rule.confidence, 4)
                    chain.append(f'{rule.antecedent} -> {rule.consequent} [{rule.source}]')
                    changed = True
            if not changed:
                break
        if target is not None and str(target) not in known:
            return RuleInference(str(target), 0.0, chain, sorted(known))
        conclusion = str(target) if target is not None else (chain[-1].split(' -> ')[-1].split(' [')[0] if chain else '')
        return RuleInference(conclusion, confidence.get(conclusion, 0.0), chain, sorted(known))

    def explain(self, facts, target):
        result = self.infer(facts, target)
        return {'conclusion': result.conclusion, 'confidence': result.confidence,
                'chain': result.chain, 'evidence': result.evidence}
