from core.semantic_verifier import SemanticVerifier


def test_accepts_aligned_answer():
    result = SemanticVerifier().verify("پایتخت ایران چیست؟", "پایتخت ایران تهران است.", ["آفلاین"])
    assert result.accepted is True


def test_rejects_network_contradiction():
    result = SemanticVerifier().verify(
        "سیستم چیست؟", "برای این کار از OpenAI API استفاده کن.", ["آفلاین", "بدون API"]
    )
    assert result.accepted is False
    assert "offline_constraint" in result.contradictions
    assert "no_api_constraint" in result.contradictions


def test_rejects_repeated_answer():
    result = SemanticVerifier().verify(
        "پایتخت ایران چیست؟", "پایتخت ایران تهران است.", [], ["پایتخت ایران تهران است."]
    )
    assert result.accepted is False
    assert "repeats_rejected_answer" in result.contradictions
