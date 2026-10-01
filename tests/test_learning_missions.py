import json
import shutil
from pathlib import Path

import pytest

from learning.missions import LearningMissionManager, format_mission_candidate_review
from runtime.app import IranRuntime


def runtime_at(tmp_path):
    shutil.copy(Path(__file__).parents[1] / "config.json", tmp_path / "config.json")
    return IranRuntime(tmp_path)


def evidence():
    return "async Python coroutine function await event loop scheduling transfer example"


def test_explicit_full_and_narrow_intents_and_normal_chat():
    full = LearningMissionManager.parse_intent("پایتون رو از صفر تا صد یادش بده")
    narrow = LearningMissionManager.parse_intent("فقط async در Python رو یاد بده")
    assert full == {"action": "create", "topic": "پایتون", "scope": "full", "explicit_add": False}
    assert narrow["action"] == "create" and narrow["scope"] == "narrow"
    assert "async" in narrow["topic"]
    assert LearningMissionManager.parse_intent("پایتون چیست؟") is None


def test_continue_status_pause_and_add_are_distinct():
    assert LearningMissionManager.parse_intent("پایتون رو ادامه بده")["action"] == "continue"
    assert LearningMissionManager.parse_intent("موضوع قبلی رو ادامه بده") is None
    assert LearningMissionManager.parse_intent("همون قبلی رو ادامه بده") is None
    assert LearningMissionManager.parse_intent("پایتون تا کجا یاد گرفته؟")["action"] == "status"
    assert LearningMissionManager.parse_intent("فعلا انگلیسی رو متوقف کن")["action"] == "pause"
    added = LearningMissionManager.parse_intent("امنیت شبکه رو هم به یادگیری اضافه کن")
    assert added["action"] == "create" and added["explicit_add"]
    assert "امنیت شبکه" in added["topic"]


def test_arbitrary_mission_and_restart_persistence(tmp_path):
    path = tmp_path / "missions.json"
    manager = LearningMissionManager(path)
    mission = manager.create("cognitive anthropology", "full", "teach me cognitive anthropology", "psychology")
    assert len(mission["units"]) >= 5
    assert all("objectives" in u and "prerequisites" in u and "mastery_threshold" in u for u in mission["units"])
    restored = LearningMissionManager(path)
    same = restored.create("cognitive anthropology", "full")
    assert same["mission_id"] == mission["mission_id"]
    assert len(restored.list()) == 1
    assert restored.get(mission["mission_id"])["domain"] == "psychology"


def test_narrow_curriculum_only_contains_scope_and_required_checkpoint(tmp_path):
    manager = LearningMissionManager(tmp_path / "m.json")
    mission = manager.create("async in Python", "narrow")
    assert len(mission["units"]) == 2
    assert "async in Python" in mission["units"][1]["title"]
    assert mission["units"][1]["prerequisites"] == [mission["units"][0]["unit_id"]]
    query = manager.search_query(mission["mission_id"], mission["units"][1]["unit_id"])
    assert "accurately" in query.lower() and "prerequisite" in query.lower()


def test_prerequisite_order_and_no_advancement_before_mastery(tmp_path):
    manager = LearningMissionManager(tmp_path / "m.json")
    mission = manager.create("network security", "narrow")
    prereq, target = mission["units"]
    assert target["unit_id"] in prereq["next_units"]
    assert manager.lesson(mission["mission_id"], target["unit_id"])["reason"] == "prerequisite_missing"
    blocked = manager.record_assessment(mission["mission_id"], target["unit_id"], .95, evidence(), transfer_success=True)
    assert blocked["reason"] == "prerequisite_missing"
    assert manager.next_unit_fair()["unit_id"] == prereq["unit_id"]


def test_assessment_failure_creates_remediation_and_no_mastery(tmp_path):
    manager = LearningMissionManager(tmp_path / "m.json")
    mission = manager.create("basic statistics", "narrow")
    unit = mission["units"][0]
    result = manager.record_assessment(mission["mission_id"], unit["unit_id"], .4, evidence(), practice_result="attempt", transfer_success=False)
    assert result["ok"] and result["remediation"]
    assert result["unit"]["status"] == "remediation"
    assert result["unit"]["fail_count"] == 1
    assert manager.get(mission["mission_id"])["progress_percent"] == 0


def test_round_robin_fairness_across_missions(tmp_path):
    manager = LearningMissionManager(tmp_path / "m.json")
    a = manager.create("astronomy concepts", "narrow")
    b = manager.create("music theory", "narrow")
    first = manager.next_unit_fair()
    second = manager.next_unit_fair()
    third = manager.next_unit_fair()
    assert first["mission_id"] == a["mission_id"]
    assert second["mission_id"] == b["mission_id"]
    assert third["mission_id"] == a["mission_id"]


def test_candidate_validation_rejects_metadata_and_topic_drift(tmp_path):
    runtime = runtime_at(tmp_path)
    try:
        mission = runtime.learning_missions.create("async in Python", "narrow")
        unit = mission["units"][0]
        drift = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                   "The textbook edition was published in 2021.", "attempt")
        assert drift["reason"] == "metadata_only"
        unrelated = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                       "Plants use sunlight for photosynthesis and energy.", "attempt")
        assert unrelated["reason"] == "topic_drift"
    finally:
        runtime.close()


def test_failed_assessment_never_creates_candidate_or_gate_proposal(tmp_path):
    runtime = runtime_at(tmp_path)
    try:
        mission = runtime.learning_missions.create("async in Python", "narrow")
        unit = mission["units"][0]
        result = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .2, evidence(), "wrong", False)
        assert result["remediation"]
        assert runtime.learning_gate.stats()["total"] == 0
        assert runtime.chatgpt_review_status()["total"] == 0
    finally:
        runtime.close()


def test_reviewer_reject_stays_terminal_and_never_reaches_human_or_gate(tmp_path):
    runtime = runtime_at(tmp_path)
    runtime.internet_access.enable()
    try:
        mission = runtime.learning_missions.create("async in Python", "narrow")
        unit = mission["units"][0]
        candidate = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                       evidence(), "executed practice", False)
        cid = candidate["candidate"]["proposal_id"]
        assert runtime.learning_gate.stats()["total"] == 0
        runtime.chatgpt_review_worker.transport = lambda row: {"learn": False, "reason": "off-topic", "confidence": .99}
        reviewed = runtime.process_one_chatgpt_learning_review()
        assert reviewed["ok"] and reviewed["learn"] is False
        assert runtime.human_learning_pending() == []
        assert runtime.learning_gate.stats()["total"] == 0
        assert runtime.chatgpt_learning_review_status(cid)["row"]["status"] == "rejected"
        assert runtime.learning_missions.get(mission["mission_id"])["candidate_history"][0]["status"] == "rejected"
    finally:
        runtime.close()


def test_end_to_end_learn_waits_for_human_approval_then_survives_restart(tmp_path):
    runtime = runtime_at(tmp_path)
    runtime.internet_access.enable()
    try:
        response = runtime.handle("فقط async در Python رو یاد بده")
        mission = runtime.learning_missions.find("async در Python")
        assert mission and "مأموریت" in response
        unit = mission["units"][0]
        outcome = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                    evidence(), "coroutine practice completed", False)
        assert outcome["ok"] and outcome["candidate"]["proposal_id"]
        cid = outcome["candidate"]["proposal_id"]
        assert runtime.learning_gate.stats()["total"] == 0
        assert runtime.learning_missions.get(mission["mission_id"])["current_unit"] == unit["unit_id"]
        runtime.chatgpt_review_worker.transport = lambda row: {"learn": True, "reason": "aligned and evidenced", "confidence": .94}
        reviewed = runtime.process_one_chatgpt_learning_review()
        assert reviewed["ok"] and reviewed["learn"] is True
        assert [r["proposal_id"] for r in runtime.human_learning_pending()] == [cid]
        assert runtime.learning_gate.stats()["total"] == 0
        assert runtime.approve_learning(cid)["reason"] == "human_confirmation_required"
        approved = runtime.approve_learning(cid, human_confirmed=True, source="tests.explicit_human")
        assert approved["ok"] and approved["proposal" ]["status"] == "approved"
        assert runtime.learning_gate.stats()["approved"] == 1
        row = runtime.chatgpt_learning_review_status(cid)["row"]
        assert row["human_source"] == "tests.explicit_human"
        assert row["gate_proposal_id"] == approved["proposal"]["proposal_id"]
        assert runtime.learning_missions.get(mission["mission_id"])["candidate_history"][0]["learned_object_id"] is not None
        after = runtime.learning_missions.get(mission["mission_id"])
        assert after["progress_percent"] == 50.0
        assert after["completed_units"] == [unit["unit_id"]]
        assert after["units"][0]["effect_status"] == "awaiting_future_observation"
    finally:
        runtime.close()
    restored = runtime_at(tmp_path)
    try:
        mission2 = restored.learning_missions.find("async در Python")
        assert mission2["progress_percent"] == 50.0
        assert mission2["current_unit"] == mission2["units"][1]["unit_id"]
        response = restored.handle("async در Python رو ادامه بده")
        assert "checkpoint" in response
    finally:
        restored.close()


def test_approval_review_format_is_candidate_specific():
    knowledge = format_mission_candidate_review({"payload": {"candidate_type": "lesson", "goal": "Physics",
        "unit_title": "Forces", "learning_objective": "Explain force", "claim": "Force is interaction",
        "why_this_should_be_learned": "Required to solve motion problems", "expected_effect": "Solve transfer task",
        "evidence": "assessment evidence", "sources": ["local source"], "practice_result": "passed",
        "assessment_result": {"passed": True}}}, {"reason": "aligned", "confidence": .9})
    skill = format_mission_candidate_review({"payload": {"candidate_type": "skill", "goal": "Programming",
        "unit_title": "Debugging", "claim": "Debug", "practice_result": "ran", "evidence": "test log",
        "assessment_result": {"transfer_success": True}}})
    language = format_mission_candidate_review({"payload": {"candidate_type": "language", "goal": "English",
        "unit_title": "Past tense", "claim": "past tense", "examples": ["I went"],
        "practice_result": "corrected", "answer_quality": "good", "assessment_result": "passed"}})
    assert "دانش پیشنهادی" in knowledge and "شواهد" in knowledge and "confidence" in knowledge
    assert "آزمایش" in skill and "آزمون انتقال" in skill
    assert "مثال‌ها" in language and "کیفیت پاسخ" in language


def test_full_course_and_english_pause_resume_commands_do_not_duplicate(tmp_path):
    runtime = runtime_at(tmp_path)
    try:
        first = runtime.handle("پایتون رو از صفر تا صد یادش بده")
        py = runtime.learning_missions.find("پایتون")
        assert "برنامهٔ درسی" in first and len(py["units"]) == 7
        runtime.handle("پایتون رو از صفر تا صد یادش بده")
        assert len([m for m in runtime.learning_missions_status() if m["normalized_topic"] == "پایتون"]) == 1
        runtime.handle("انگلیسی رو هم به یادگیری اضافه کن")
        english = runtime.learning_missions.find("انگلیسی")
        assert english and english["mission_id"] != py["mission_id"]
        runtime.handle("فعلا انگلیسی رو متوقف کن")
        assert runtime.learning_missions.get(english["mission_id"])["status"] == "paused"
        continued = runtime.handle("انگلیسی رو ادامه بده")
        assert "checkpoint" in continued
        assert runtime.learning_missions.get(english["mission_id"])["status"] == "active"
        assert len(runtime.learning_missions_status()) == 2
    finally:
        runtime.close()


def test_effect_learning_updates_mission_and_weak_effect_triggers_remediation(tmp_path):
    runtime = runtime_at(tmp_path)
    try:
        mission = runtime.learning_missions.create("music theory", "narrow")
        unit = mission["units"][0]
        assessed = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                     "music theory notes harmony rhythm scale application", "passed")
        cid = assessed["candidate"]["proposal_id"]
        runtime.internet_access.enable()
        runtime.chatgpt_review_worker.transport = lambda row: {"learn": True, "reason": "supported", "confidence": .9}
        assert runtime.process_one_chatgpt_learning_review()["learn"]
        assert runtime.approve_learning(cid, human_confirmed=True, source="effect_fixture")["ok"]
        effect = runtime.record_mission_effect(mission["mission_id"], unit["unit_id"], True, .4,
                                               "transfer task failed", transfer_success=False)
        assert effect["ok"] and effect["effect_learning"]["effect"] == "unverified"
        updated = runtime.learning_missions.get(mission["mission_id"])
        assert updated["units"][0]["effect_status"] == "weak_effect"
        assert updated["next_action"] == "effect_remediation"
    finally:
        runtime.close()


def test_duplicate_assessment_reuses_candidate_and_does_not_duplicate_queue(tmp_path):
    runtime = runtime_at(tmp_path)
    try:
        mission = runtime.learning_missions.create("basic astronomy", "narrow")
        unit = mission["units"][0]
        first = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                  "astronomy stars galaxy orbital observation evidence", "passed")
        second = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                   "astronomy stars galaxy orbital observation evidence", "passed")
        assert first["candidate"]["proposal_id"] == second["candidate"]["proposal_id"]
        assert runtime.chatgpt_review_status()["total"] == 1
    finally:
        runtime.close()


def test_approval_crash_rolls_back_mission_gate_and_review_together(tmp_path, monkeypatch):
    runtime = runtime_at(tmp_path)
    runtime.internet_access.enable()
    try:
        mission = runtime.learning_missions.create("basic ecology", "narrow")
        unit = mission["units"][0]
        staged = runtime.submit_mission_assessment(mission["mission_id"], unit["unit_id"], .95,
                                                   "ecology ecosystem species energy environment observation", "passed")
        cid = staged["candidate"]["proposal_id"]
        runtime.chatgpt_review_worker.transport = lambda row: {"learn": True, "reason": "supported", "confidence": .9}
        assert runtime.process_one_chatgpt_learning_review()["learn"]
        emit = runtime.events.emit
        def fail_after_apply(event, payload=None):
            if event == "learning_approved":
                raise RuntimeError("simulated crash after mission update")
            return emit(event, payload)
        monkeypatch.setattr(runtime.events, "emit", fail_after_apply)
        with pytest.raises(RuntimeError, match="simulated crash"):
            runtime.approve_learning(cid, human_confirmed=True, source="crash_test_human")
        assert runtime._recovery_required
    finally:
        runtime.close()
    restored = runtime_at(tmp_path)
    try:
        mission_after = restored.learning_missions.get(mission["mission_id"])
        assert mission_after["progress_percent"] == 0
        assert mission_after["units"][0]["status"] == "waiting_for_human"
        assert restored.learning_gate.stats()["pending"] == 1
        review = restored.chatgpt_learning_review_status(cid)["row"]
        assert review["status"] == "human_pending"
        approved = restored.approve_learning(cid, human_confirmed=True, source="recovered_human")
        assert approved["ok"]
        assert restored.learning_missions.get(mission["mission_id"])["progress_percent"] == 50.0
    finally:
        restored.close()
