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


def test_negated_fact_is_not_supported_by_shared_words():
    fact={'subject':'ایران','predicate':'پایتخت','object':'تهران'}
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','تهران پایتخت ایران نیست.',evidence=[fact])
    assert not result.accepted and result.evidence_status=='REFUTED'


def test_mentioning_fact_value_in_unrelated_clause_is_not_support():
    fact={'subject':'ایران','predicate':'پایتخت','object':'تهران'}
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','پایتخت ایران شیراز است؛ تهران یک شهر است.',evidence=[fact])
    assert not result.accepted


def test_conflicting_single_valued_facts_require_resolution():
    facts=[{'subject':'ایران','predicate':'پایتخت','object':city,'source':city} for city in ('تهران','شیراز')]
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','تهران',evidence=facts)
    assert not result.accepted and result.evidence_status=='CONFLICTING'
    assert set(result.evidence_sources)=={'تهران','شیراز'}


def test_superseded_fact_is_not_an_active_conflict():
    facts=[{'subject':'ایران','predicate':'پایتخت','object':'تهران'},
           {'subject':'ایران','predicate':'پایتخت','object':'شیراز','superseded':True,'contradicted_by':{'object':'تهران'}}]
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','تهران',evidence=facts)
    assert result.accepted and result.evidence_status=='SUPPORTED'


def test_multiple_preferences_are_not_single_valued_conflict():
    facts=[{'subject':'user','predicate':'likes','object':v} for v in ('موسیقی','برنامه نویسی')]
    result=SemanticVerifier().verify('درباره خودم چه گفتم؟','موسیقی و برنامه نویسی را دوست داری.',evidence=facts)
    assert result.accepted and result.evidence_status=='SUPPORTED'


def test_legacy_contradiction_marker_does_not_resolve_conflict():
    facts=[{'subject':'ایران','predicate':'پایتخت','object':'تهران','contradicted_by':{'object':'شیراز'}},
           {'subject':'ایران','predicate':'پایتخت','object':'شیراز'}]
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','شیراز',evidence=facts)
    assert not result.accepted and result.evidence_status=='CONFLICTING'


def test_explicit_correction_can_reactivate_prior_value_after_restart(tmp_path):
    from knowledge.knowledge_graph import KnowledgeGraph
    path=tmp_path/'facts.json'
    graph=KnowledgeGraph(path)
    graph.add_fact('ایران','پایتخت','تهران')
    graph.contradict('ایران','پایتخت','شیراز')
    graph=KnowledgeGraph(path)
    graph.contradict('ایران','پایتخت','تهران')
    graph=KnowledgeGraph(path)
    result=SemanticVerifier().verify('پایتخت ایران کجاست؟','تهران',evidence=graph.facts)
    assert result.accepted and result.evidence_status=='SUPPORTED'
    assert len(graph.facts)==2
