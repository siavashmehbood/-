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

    def prove(self, facts, target, max_depth=6):
        """Backward chaining: search for a proof of `target` from the facts.

        `infer` only answers whether forward chaining happened to reach `target`. This
        asks the opposite question - which rules could derive it, and are their
        antecedents themselves derivable? - which is how a goal is checked against the
        rules before committing to an answer.

        Confidence is the product of antecedent confidences and each rule's own
        confidence along the chosen proof; when several rules could prove the target,
        the most confident proof wins. A literal already present as a fact is proved
        with confidence 1.0.

        Cycles are guarded: `visiting` breaks a recursion that would otherwise not
        terminate on a rule set such as A -> B, B -> A.
        """
        target = str(target)
        facts = [str(f) for f in facts or []]
        fact_set = set(facts)

        def _prove(goal, depth, visiting):
            if goal in fact_set:
                return 1.0, [f'fact: {goal}']
            if depth <= 0 or goal in visiting:
                return None, []
            local_best = None
            for rule in self.rules:
                if str(rule.consequent) != goal:
                    continue
                antecedent = str(rule.antecedent)
                sub_confidence, sub_proof = _prove(antecedent, depth - 1, visiting | {goal})
                if sub_confidence is None:
                    continue
                combined = round(sub_confidence * float(rule.confidence), 4)
                link = f'{antecedent} -> {goal} [{rule.source}]'
                if local_best is None or combined > local_best[0]:
                    local_best = (combined, sub_proof + [link])
            return local_best if local_best is not None else (None, [])

        confidence, proof = _prove(target, int(max_depth), frozenset())
        if confidence is None:
            # Report which antecedents blocked the search, so a failure is diagnosable
            # instead of just "not proved".
            unresolved = sorted({
                str(rule.antecedent) for rule in self.rules
                if str(rule.consequent) == target and str(rule.antecedent) not in fact_set
            })
            return {'proved': False, 'confidence': 0.0, 'proof': [], 'unresolved': unresolved}
        return {'proved': True, 'confidence': confidence, 'proof': proof, 'unresolved': []}

    def contradictions(self, facts, target=None):
        """Find literals that are both derivable and explicitly negated.

        Negation is expressed with a `not:` prefix (`not:باران`), which keeps the fact
        format a plain string and needs no new type. A literal is contradictory when it
        is provable and its negation is present as a fact, or when both forms are
        present directly.
        """
        facts = [str(f) for f in facts or []]
        fact_set = set(facts)
        candidates = {target.split(':', 1)[-1] if target and target.startswith('not:') else target} if target else set()
        if target is None:
            candidates = {f.split(':', 1)[1] for f in fact_set if f.startswith('not:')}
            candidates |= {str(rule.consequent) for rule in self.rules}
        found = []
        for literal in sorted(candidates):
            if not literal:
                continue
            negated = f'not:{literal}'
            present_positive = literal in fact_set
            present_negative = negated in fact_set
            proved_positive = self.prove(facts, literal)['proved']
            if (present_positive and present_negative) or (proved_positive and present_negative):
                found.append({
                    'literal': literal,
                    'positive_confidence': 1.0 if present_positive else self.prove(facts, literal)['confidence'],
                    'negation_evidence': negated,
                })
        return found
