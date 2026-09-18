import json
from learning.learning_engine import LearningEngine
from learning.effect_loop import EffectLearningLoop


def test_verified_success_awards_xp_once_and_persists(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    v={"verified":True,"score":.95,"source":"test"}
    a=loop.evaluate("هدف الف","روش الف","نتیجه درست","نتیجه",v,"strategy-a","task","e1",1)
    b=loop.evaluate("هدف الف","روش الف","نتیجه درست","نتیجه",v,"strategy-a","task","e1",1)
    assert a["xp_awarded"]==1000000
    assert b["xp_awarded"]==0
    assert loop.stats()["xp"]==1000000
    assert json.loads((tmp_path/"effect.json").read_text(encoding="utf-8"))["xp"]==1000000


def test_negative_verified_outcome_is_negative_evidence(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    engine.rules=[{"rule":"r","intent":"verified_outcome","domain":"task","strategy":"bad","confidence":.80}]
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    out=loop.evaluate("هدف","bad","wrong","correct",{"verified":True,"score":0.1},"bad","task","e2",1)
    assert out["rule_updates"][0]["new"] < .80


def test_rule_retires_after_repeated_verified_failures(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    engine.rules=[{"rule":"r","intent":"verified_outcome","domain":"task","strategy":"bad","confidence":.30,"failed_uses":1}]
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    out=loop.evaluate("هدف","bad","wrong","correct",{"verified":True,"score":0.1},"bad","task","e3",2)
    assert out["rule_updates"][0]["status"]=="retired"


def test_meta_learning_selects_active_evidence_when_no_rule(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    out=loop.recommend_meta_strategy("موضوع جدید","general","task")
    assert out["mode"]=="active-evidence"
    assert out["exploration_required"] is True


def test_active_learning_requests_only_for_uncertainty_or_novelty(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    assert loop.active_learning_request("x",.2,.1)["needed"] is False
    assert loop.active_learning_request("x",.8,.1)["needed"] is True
    assert loop.active_learning_request("x",.2,.8)["needed"] is True
def test_success_recommends_transfer_retest(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    out=loop.evaluate("هدف","روش","ok","ok",{"verified":True,"score":.9},"s","task","e",1)
    assert out["next_test"]["mode"]=="retest_transfer"


def test_failure_recommends_strategy_change(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    out=loop.evaluate("هدف","روش","bad","ok",{"verified":True,"score":.2},"s","task","e",1)
    assert out["next_test"]["mode"]=="change_strategy"


def test_learning_stats_survive_restart(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    path=tmp_path/"effect.json"; loop=EffectLearningLoop(path,engine)
    loop.evaluate("هدف","روش","ok","ok",{"verified":True,"score":.9},"s","task","e",1)
    restored=EffectLearningLoop(path,LearningEngine(tmp_path/"experiences2.json"))
    assert restored.stats()["xp"]==1000000


def test_replay_prioritizes_uncertain_and_failed_evidence(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    loop.evaluate("g","a","x","x",{"verified":True,"score":.50},"s","task","e1",1)
    loop.evaluate("g","b","x","x",{"verified":True,"score":.95},"s2","task","e2",1)
    rows=loop.replay_candidates(2)
    assert rows[0]["strategy"]=="s"


def test_strategy_comparison_uses_verified_history(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    for i in range(2):
        loop.evaluate("g","a","ok","ok",{"verified":True,"score":.9},"good","task",f"g{i}",1)
        loop.evaluate("g","b","bad","ok",{"verified":True,"score":.4},"bad","task",f"b{i}",1)
    rows=loop.compare_strategies("g","task")
    assert rows[0]["strategy"]=="good"
    assert rows[0]["mean_score"]>.8


def test_learning_priority_prefers_verified_strategy_when_supported(tmp_path):
    engine=LearningEngine(tmp_path/"experiences.json")
    loop=EffectLearningLoop(tmp_path/"effect.json",engine)
    for i in range(2):
        loop.evaluate("g","a","ok","ok",{"verified":True,"score":.9},"good","task",f"e{i}",1)
    out=loop.learning_priority("g","general","task",.2,.1)
    assert out["action"]=="reuse_best_then_verify"
