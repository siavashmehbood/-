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


def test_unrelated_declarative_answer_is_not_accepted():
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','موز یک میوه است.')
    assert not result.accepted
    assert 'unrelated_answer' in result.reasons


def test_unrelated_answer_with_generic_question_words_is_not_accepted():
    result=SemanticVerifier().verify('درباره مدار زمین توضیح بده','این پاسخ درباره قیمت خودرو است.')
    assert not result.accepted


def test_short_answer_supported_by_relevant_evidence():
    evidence=[{'subject':'ایران','predicate':'پایتخت','object':'تهران','source':'fixture'}]
    assert SemanticVerifier().verify('پایتخت ایران کجاست؟','تهران',evidence=evidence).accepted
    assert not SemanticVerifier().verify('پایتخت ایران کجاست؟','شیراز',evidence=evidence).accepted


def test_unrelated_evidence_does_not_authorize_answer():
    evidence=[{'subject':'موز','predicate':'نوع','object':'میوه'}]
    assert not SemanticVerifier().verify('پایتخت ایران کجاست؟','میوه است.',evidence=evidence).accepted


def test_greeting_and_explicit_uncertainty_are_not_factual_claims():
    assert SemanticVerifier().verify('سلام','درود!').accepted
    result=SemanticVerifier().verify('پایتخت کشور ناشناخته کجاست؟','UNKNOWN: شواهد کافی ندارم.')
    assert result.status=='UNKNOWN'
