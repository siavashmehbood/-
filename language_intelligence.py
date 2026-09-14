"""Structured Persian language intelligence facade over the existing engine.
Keeps the current engine as the source of truth and exposes a stable semantic contract.
"""
import re
from core.language_engine import PersianLanguageEngine

class PersianIntelligence:
    def __init__(self, engine=None):
        self.engine = engine or PersianLanguageEngine()

    def analyze(self, raw_text, frame=None):
        raw = str(raw_text)
        result = self.engine.analyze(raw)
        parsed = self.engine.advanced.parse(raw, frame or {})
        constraints = []
        for m in re.finditer(r"(?:بدون|فقط|نباید|حتماً|حداقل|حداکثر|ترجیحاً|لازم نیست|فعلاً)\s+[^،؛.?!؟]+", result.normalized):
            value = m.group(0).strip()
            if value not in constraints:
                constraints.append(value)
        intents = parsed.get('intents') or [
            {'name': result.intent, 'score': result.confidence, 'evidence': []}
        ]
        return {
            'raw_text': raw,
            'normalized_text': result.normalized,
            'language': result.language,
            'intent': result.intent,
            'intents': intents,
            'multi_intent': len(intents) > 1,
            'entities': result.entities_typed,
            'constraints': constraints,
            'negations': result.negated,
            'temporal': parsed.get('temporal_expressions', []),
            'references': parsed.get('reference_candidates', {}),
            'questions': parsed.get('question_units', []),
            'subgoals': parsed.get('subgoals', []),
            'ambiguity': result.ambiguity,
            'confidence': result.confidence,
            'goal': result.goal,
            'requested_output': None,
        }
