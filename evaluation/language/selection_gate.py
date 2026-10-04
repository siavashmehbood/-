"""Hard promotion gates for Persian excellence without multilingual collapse."""
from __future__ import annotations


class SelectionGate:
    PERSIAN_MIN = 80.0
    MULTILINGUAL_AVG_MIN = 75.0
    LANGUAGE_MIN = 60.0
    MULTILINGUAL_MAX_LOSS = 3.0
    CRITICAL_LANGUAGE_MAX_LOSS = 2.0
    CAPABILITY_MAX_LOSS = 3.0
    CRITICAL_LANGUAGES = ("en", "ar", "tr")

    def evaluate(self, candidate, baseline=None):
        baseline = baseline or {}
        reasons = []
        persian = float(candidate.get("persian", 0))
        languages = {str(k): float(v) for k, v in candidate.get("languages", {}).items()}
        if persian < self.PERSIAN_MIN:
            reasons.append("persian_below_80")
        if not languages:
            reasons.append("missing_multilingual_scores")
        else:
            average = sum(languages.values()) / len(languages)
            if average < self.MULTILINGUAL_AVG_MIN:
                reasons.append("multilingual_average_below_75")
            if any(v < self.LANGUAGE_MIN for v in languages.values()):
                reasons.append("tier1_language_below_60")

        base_languages = {str(k): float(v) for k, v in baseline.get("languages", {}).items()}
        shared = set(languages) & set(base_languages)
        if shared:
            current_avg = sum(languages[k] for k in shared) / len(shared)
            base_avg = sum(base_languages[k] for k in shared) / len(shared)
            if base_avg - current_avg > self.MULTILINGUAL_MAX_LOSS:
                reasons.append("multilingual_regression_gt_3")
            for code in self.CRITICAL_LANGUAGES:
                if code in shared and base_languages[code] - languages[code] > self.CRITICAL_LANGUAGE_MAX_LOSS:
                    reasons.append(f"{code}_regression_gt_2")

        for capability in ("reasoning", "code", "instruction"):
            if capability in baseline and capability in candidate:
                if float(baseline[capability]) - float(candidate[capability]) > self.CAPABILITY_MAX_LOSS:
                    reasons.append(f"{capability}_regression_gt_3")

        if candidate.get("iran_regressions", 0):
            reasons.append("iran_regression")
        if candidate.get("one_brain") is False:
            reasons.append("one_brain_violation")
        if candidate.get("offline") is False:
            reasons.append("offline_gate_failed")
        if candidate.get("hidden_gate") is False:
            reasons.append("hidden_gate_failed")
        return {"passed": not reasons, "reasons": reasons}
