from learning.self_directed import SelfDirectedLearning


def test_unrelated_evidence_is_rejected():
    s = SelfDirectedLearning()
    result = s.assess("تاریخچه X", "history edit navigation computer virus", "", .9)
    assert result["learn"] is False
    assert result["reason"] == "topic_mismatch"


def test_relevant_evidence_creates_goal():
    s = SelfDirectedLearning()
    result = s.goal_for("Python حلقه", "در Python حلقه for برای تکرار استفاده می‌شود", "", .9)
    assert result["decision"]["learn"] is True
    assert result["topic"] == "Python حلقه"
    assert result["status"] == "needs_evidence"


def test_low_confidence_does_not_trigger_learning():
    s = SelfDirectedLearning()
    result = s.assess("ریاضی", "ریاضی جبر معادله", "", .2)
    assert result["learn"] is False
    assert result["reason"] == "weak_evidence"
