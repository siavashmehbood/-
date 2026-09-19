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


def test_novelty_is_lower_when_fact_is_already_known():
    s = SelfDirectedLearning()
    result = s.assess("Python حلقه", "Python حلقه for برای تکرار است", "Python حلقه for برای تکرار است", .9)
    assert result["novelty"] < .08
    assert result["reason"] == "already_known_or_low_novelty"


def test_conflict_requires_resolution():
    s = SelfDirectedLearning()
    result = s.assess("پایتخت ایران", "پایتخت ایران تهران نیست", "پایتخت ایران تهران است", .9)
    assert result["needs_resolution"] is True
    assert result["reason"] == "relevant_conflict_requires_resolution"


def test_domain_and_next_action_are_deterministic():
    s = SelfDirectedLearning()
    goal = s.goal_for("Python حلقه", "در Python حلقه for تکرار می‌کند", "", .9)
    assert goal["domain"] == "programming"
    assert s.next_action(goal)["action"] == "collect_relevant_evidence"


def test_goal_outcome_is_persisted(tmp_path):
    path = tmp_path / "goals.json"
    s = SelfDirectedLearning(path)
    goal = s.create_goal("ریاضی", domain="mathematics")
    s.update_outcome(goal["goal_id"], "testing", 2, True)
    restored = SelfDirectedLearning(path)
    assert restored.snapshot()["count"] == 1
    assert restored.snapshot()["goals"][0]["success_count"] == 1


def test_foundational_curriculum_is_broad_and_idempotent(tmp_path):
    path = tmp_path / "goals.json"
    s = SelfDirectedLearning(path)
    first = s.curriculum_batch(200)
    second = s.curriculum_batch(200)
    assert len(first) >= 100
    assert len(second) == 200
    assert len({row["key"] for row in first}) == len(first)
    assert len(s.CURRICULUM) >= 20
    required = {
        "mathematics", "programming", "computer_science",
        "artificial_intelligence", "english", "persian_literature",
        "english_literature", "physics", "chemistry", "biology",
    }
    assert required.issubset(s.CURRICULUM)
    assert sum(len(v) for v in s.CURRICULUM.values()) >= 120


def test_curriculum_domain_detection_covers_core_subjects():
    s = SelfDirectedLearning()
    assert s.detect_domain("حل معادله درجه دوم") == "mathematics"
    assert s.detect_domain("تابع پایتون") == "programming"
    assert s.detect_domain("گرامر زبان انگلیسی") == "english"
    assert s.detect_domain("تحلیل یک شعر انگلیسی") == "english_literature"
    assert s.detect_domain("شبکه عصبی در هوش مصنوعی") == "artificial_intelligence"
    assert s.detect_domain("واکنش شیمیایی") == "chemistry"
    assert s.detect_domain("ژنتیک و سلول") == "biology"
