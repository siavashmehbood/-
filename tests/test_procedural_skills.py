from core.procedural_skills import ProceduralSkillMemory


def test_skill_requires_repeated_verified_success(tmp_path):
    memory = ProceduralSkillMemory(tmp_path / "skills.json")
    rows = [
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix parser error", "action": "inspect traceback", "expected": "error isolated", "timestamp": "2026-01-01T00:00:00"},
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix runtime error", "action": "inspect traceback", "expected": "error isolated", "timestamp": "2026-01-02T00:00:00"},
    ]
    assert memory.promote(rows, "debug", "inspect-first")["source_experiences"] == 2
    assert memory.stats()["skills"] == 1


def test_skill_transfer_is_symbolic_and_reusable(tmp_path):
    memory = ProceduralSkillMemory(tmp_path / "skills.json")
    rows = [
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix parser error", "action": "inspect traceback", "expected": "isolated", "timestamp": "2026-01-01T00:00:00"},
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix runtime error", "action": "inspect logs", "expected": "isolated", "timestamp": "2026-01-02T00:00:00"},
    ]
    memory.promote(rows, "debug", "inspect-first")
    result = memory.prepare_transfer("fix parser crash", domain="debug")
    assert result["candidates"]
    skill_id = result["candidates"][0]["skill"]["id"]
    before = result["candidates"][0]["skill"]["trust"]
    after = memory.observe(skill_id, True, .9)
    assert after["trust"] > before


def test_failed_transfer_reduces_trust(tmp_path):
    memory = ProceduralSkillMemory(tmp_path / "skills.json")
    rows = [
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix parser error", "action": "inspect traceback", "expected": "isolated", "timestamp": "2026-01-01T00:00:00"},
        {"verified": True, "score": .9, "domain": "debug", "strategy": "inspect-first", "goal": "fix runtime error", "action": "inspect logs", "expected": "isolated", "timestamp": "2026-01-02T00:00:00"},
    ]
    skill = memory.promote(rows, "debug", "inspect-first")
    after = memory.observe(skill["name"], False, 0.2)
    assert after["trust"] < skill["trust"]
