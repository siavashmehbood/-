from datetime import datetime


def pattern_feedback(self, pattern_key, score, verified=True, reason=''):
    if not verified:
        return None
    pattern = next((p for p in self.patterns if p.get('pattern_key') == pattern_key), None)
    if not pattern:
        return None
    score = max(0.0, min(1.0, float(score)))
    successes = int(pattern.get('success_count', 0))
    failures = int(pattern.get('failure_count', 0))
    if score >= 0.67:
        successes += 1
    else:
        failures += 1
    total = successes + failures
    target = successes / max(1, total)
    prior = float(pattern.get('confidence', 0.45))
    confidence = max(0.05, min(0.95, prior * 0.65 + target * 0.35))
    status = 'active' if confidence >= 0.55 and successes >= failures else ('weakened' if confidence >= 0.30 else 'retired')
    pattern.update({
        'success_count': successes,
        'failure_count': failures,
        'confidence': round(confidence, 4),
        'status': status,
        'last_feedback': round(score, 4),
        'feedback_reason': str(reason)[:300],
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    })
    self._save_patterns()
    return dict(pattern)
