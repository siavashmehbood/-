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
