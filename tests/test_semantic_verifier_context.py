"""Regression tests for evidence-scoped semantic verification."""
from core.semantic_verifier import SemanticVerifier


def test_supported_fact_can_be_restated_after_prior_contextual_rejection():
    verifier=SemanticVerifier()
    answer='هدف ثبت‌شده برای «دانا»: «فروش کتاب».'
    evidence=[{
        "subject":"دانا","predicate":"هدف","object":"فروش کتاب",
        "source":"conversation_state","resolved":True,
    }]
    result=verifier.verify(
        "هدفش چی بود؟",answer,
        evidence=evidence,
        rejected_answers=[answer],
    )
    assert result.accepted, result
    assert result.evidence_status=="SUPPORTED"
    assert "repeats_rejected_answer" not in result.contradictions


def test_unsupported_repeat_of_rejected_answer_still_fails_closed():
    verifier=SemanticVerifier()
    answer="پاسخ قبلی اشتباه بود و باید دوباره تکرار شود."
    result=verifier.verify(
        "جواب درست چیه؟",answer,
        evidence=[],
        rejected_answers=[answer],
    )
    assert not result.accepted
    assert "repeats_rejected_answer" in result.contradictions
