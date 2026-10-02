"""Durable, subject-agnostic learning mission planning and progress tracking.

The manager owns curriculum/progress state only. Candidate review and durable
learning remain in the canonical candidate -> reviewer -> human -> Gate path.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import re
from pathlib import Path

from persistence import json_transaction, load_critical_json


ACTIVE_STATUSES = {
    "planned", "building_curriculum", "active", "waiting_for_evidence",
    "waiting_for_reviewer", "waiting_for_human", "practicing", "assessing",
    "blocked", "paused",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(text):
    text = str(text or "").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", text).strip(" ،,؛;.!؟?\"'«»")


def _key(text):
    return _clean(text).lower()


def format_mission_candidate_review(row, reviewer=None):
    """Render candidate-specific review fields without implying generic actions."""
    row = row or {}
    reviewer = reviewer or {}
    payload = row.get("payload", {}) or {}
    kind = str(payload.get("candidate_type", "lesson")).lower()
    mission = str(payload.get("mission_title", payload.get("goal", row.get("summary", "—"))))
    unit = str(payload.get("unit_title", payload.get("unit_id", "—")))
    review = [f"مأموریت: {mission}", f"مرحله / درس: {unit}",
              f"هدف یادگیری: {payload.get('learning_objective', '—')}"]
    if kind in {"skill", "procedure", "skill_candidate"}:
        review.extend((f"مهارت/رویه: {payload.get('claim', payload.get('lesson', '—'))}",
                       f"آزمایش: {payload.get('practice_result', '—')}",
                       f"شواهد اجرایی: {payload.get('evidence', '—')}",
                       f"آزمون انتقال: {payload.get('assessment_result', {}).get('transfer_success', '—') if isinstance(payload.get('assessment_result'), dict) else '—'}",
                       f"نتیجه: {payload.get('assessment_result', '—')}"))
    elif kind in {"language", "language_lesson", "language_candidate"}:
        review.extend((f"مفهوم: {payload.get('claim', payload.get('lesson', '—'))}",
                       f"مثال‌ها: {payload.get('examples', '—')}",
                       f"تمرین: {payload.get('practice_result', '—')}",
                       f"کیفیت پاسخ: {payload.get('answer_quality', '—')}",
                       f"ارزیابی: {payload.get('assessment_result', '—')}"))
    else:
        review.extend((f"دانش پیشنهادی: {payload.get('claim', payload.get('lesson', '—'))}",
                       f"چرا این دانش مفید است: {payload.get('why_this_should_be_learned', '—')}",
                       f"اثر مورد انتظار: {payload.get('expected_effect', '—')}",
                       f"شواهد: {payload.get('evidence', '—')}",
                       f"منابع: {payload.get('sources', '—')}",
                       f"تمرین انجام‌شده: {payload.get('practice_result', '—')}",
                       f"نتیجه ارزیابی: {payload.get('assessment_result', '—')}"))
    review.extend((f"نظر مدل رایگان: {reviewer.get('reason', reviewer.get('answer', '—'))}",
                   f"confidence: {reviewer.get('confidence', '—')}",
                   f"وضعیت: {row.get('status', '—')}"))
    return "\n".join(review)


class LearningMissionManager:
    """Stores resumable learning missions with generic dependency-aware paths."""
    SCHEMA_VERSION = 1
    FULL_STAGES = (
        ("foundation", "Foundations and prerequisite concepts"),
        ("basic", "Core vocabulary, elements, and basic operations"),
        ("basic", "Core relationships, rules, or procedures"),
        ("intermediate", "Methods, patterns, and structured problem solving"),
        ("intermediate", "Applied practice and common failure modes"),
        ("advanced", "Advanced cases, trade-offs, and transfer"),
        ("evaluation", "Integrated project, evaluation, and consolidation"),
    )

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._validate(load_critical_json(self.path, self._default()))

    @staticmethod
    def _default():
        return {"schema_version": 1, "missions": [], "scheduler": {"last_mission_id": None}}

    @staticmethod
    def _validate(state):
        if not isinstance(state, dict) or not isinstance(state.get("missions", []), list):
            raise ValueError("invalid learning missions state")
        return state

    @contextmanager
    def _tx(self):
        with json_transaction(self.path, self._default()) as state:
            self._validate(state)
            state.setdefault("schema_version", self.SCHEMA_VERSION)
            state.setdefault("missions", [])
            state.setdefault("scheduler", {"last_mission_id": None})
            yield state

    @staticmethod
    def parse_intent(text):
        """Return an intent only for clear learning/status/pause/resume language."""
        raw = _clean(text)
        t = raw.lower().replace("ي", "ی").replace("ك", "ک")
        if not raw:
            return None
        status_marks = ("تا کجا", "چقدر یاد", "وضعیت مأموریت", "وضعیت ماموریت", "mission status", "how far")
        if any(mark in t for mark in status_marks):
            topic = re.split(r"تا کجا|چقدر یاد|وضعیت مأموریت|وضعیت ماموریت|mission status|how far", raw, flags=re.I)[0]
            topic = re.sub(r"(رو|را|ـ|موضوع)\s*$", "", topic).strip()
            return {"action": "status", "topic": topic}
        if any(mark in t for mark in ("فعلا", "فعلاً", "موقتاً", "موقتا")) and any(x in t for x in ("متوقف", "pause", "بس کن")):
            topic = re.sub(r"^(فعلا|فعلاً|موقتا|موقتاً)\s*", "", raw, flags=re.I)
            topic = re.sub(r"\s*(رو|را)?\s*(متوقف کن|متوقف|pause|بس کن).*$", "", topic, flags=re.I)
            return {"action": "pause", "topic": topic.strip()}
        if any(x in t for x in ("ادامه بده", "ادامه‌ش بده", "ادامه اش بده", "ادامه کن", "ادامه بدهید", "continue", "resume")):
            topic = re.split(r"ادامه(?:ش| اش)?\s*(?:بده|کن|بدهید)?|continue|resume", raw, maxsplit=1, flags=re.I)[0]
            topic = re.sub(r"\s*(رو|را)\s*$", "", topic).strip()
            reference_only = ("موضوع قبلی", "همون قبلی", "همان قبلی", "قبلی رو", "قبلی را",
                              "همونو", "همان را", "اون رو", "آن را", "previous topic", "the previous one", "that")
            if any(marker in t for marker in reference_only) or _key(topic) in {"", "یادگیری", "مأموریت", "ماموریت", "موضوع"}:
                return None
            return {"action": "continue", "topic": topic}
        add_marks = ("به یادگیری اضافه کن", "به یادگیری اضافه", "اضافه کن به یادگیری", "add to learning", "add .* to my learning")
        if any(re.search(mark, t) for mark in add_marks):
            topic = re.split(r"(?:رو|را)?\s*(?:هم\s*)?(?:به یادگیری اضافه کن|به یادگیری اضافه|اضافه کن به یادگیری|add to learning)", raw, maxsplit=1, flags=re.I)[0]
            topic = re.sub(r"\s*(رو|را)\s*$", "", topic).strip()
            topic = re.sub(r"^(این موضوع|موضوع)\s*", "", topic)
            return {"action": "create", "topic": topic, "scope": "full", "explicit_add": True} if topic else None
        learn_marks = ("یادش بده", "یاد بده", "یاد بدهید", "آموزش بده", "آموزش بدهید", "یاد بگیر", "یاد بگیرم", "teach me", "teach ", "learn ")
        if any(mark in t for mark in learn_marks):
            # Topic is the explicit object before the learning verb.
            matches = [t.find(mark) for mark in learn_marks if mark in t]
            topic = raw[:min(matches)] if matches else ""
            topic = re.sub(r"\b(?:teach me|teach|learn)\b.*$", "", topic, flags=re.I)
            topic = re.sub(r"^(?:لطفا|لطفاً)\s*", "", topic, flags=re.I)
            topic = re.sub(r"^(فقط|صرفا|صرفاً|only|just)\s*", "", topic, flags=re.I)
            topic = re.sub(r"\s*(رو|را|را به من|رو به من)\s*$", "", topic, flags=re.I)
            topic = re.sub(r"\s*(?:از صفر تا صد|از پایه تا پیشرفته|از پایه|از صفر|کامل|از ابتدا|from scratch|from the beginning|from basics to advanced).*$", "", topic, flags=re.I)
            topic = re.sub(r"\s*(رو|را)\s*$", "", topic, flags=re.I)
            if not topic:
                return None
            narrow = bool(re.search(r"(?:^|\s)(?:فقط|صرفا|صرفاً|only|just)(?:\s|$)", t))
            full = bool(re.search(r"از صفر تا صد|از پایه تا پیشرفته|کامل|from scratch|from basics to advanced|full course", t))
            return {"action": "create", "topic": _clean(topic), "scope": "narrow" if narrow and not full else "full", "explicit_add": False}
        return None

    @staticmethod
    def _stable_id(topic, scope):
        return "mission_" + hashlib.sha256((_key(topic) + "|" + scope).encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _unit(unit_id, title, description, level, stage, prerequisites, index, topic):
        objective = f"Explain, apply, and assess {title} in the context of {topic}."
        return {
            "unit_id": unit_id, "title": title, "description": description,
            "level": level, "stage": stage, "objectives": [objective],
            "prerequisites": list(prerequisites), "concepts": [topic, title],
            "expected_knowledge": f"Learner can accurately explain {title}.",
            "expected_skill": f"Learner can apply {title} to a new example.",
            "lesson_type": "guided_explanation_and_application",
            "evidence_requirements": ["traceable sources or explicit local instructional provenance"],
            "practice_requirements": ["attempt a worked example and a novel transfer task"],
            "assessment_requirements": ["recall plus application/transfer where applicable"],
            "mastery_threshold": 0.8, "failure_remediation": "Review weak concepts, practice a simpler example, then reassess.",
            "next_units": [], "status": "planned", "attempts": 0, "pass_count": 0,
            "fail_count": 0, "mastery_score": 0.0, "weak_concepts": [],
            "remediation_count": 0, "transfer_success": False,
            "assessment_history": [], "evidence_history": [], "candidate_history": [],
            "approved_learning_ids": [], "effect_status": "not_observed",
            "order": index,
        }

    @classmethod
    def build_curriculum(cls, topic, scope="full"):
        topic = _clean(topic)
        words = re.findall(r"[\wآ-ی.+#-]+", topic)
        focus = topic
        # Narrow focus paths add a generic readiness/prerequisite checkpoint, not
        # domain-specific invented course content.
        if scope == "narrow":
            prerequisite_id = "unit_" + hashlib.sha256((topic + "|readiness").encode()).hexdigest()[:12]
            target_id = "unit_" + hashlib.sha256((topic + "|focus").encode()).hexdigest()[:12]
            prerequisite = cls._unit(prerequisite_id, f"Prerequisite check for {focus}",
                                     f"Identify and verify the concepts needed before studying {focus}; record gaps rather than assuming prior knowledge.",
                                     "foundation", "foundation", [], 0, topic)
            target = cls._unit(target_id, f"Focused study: {focus}",
                               f"Study only {focus} and the prerequisites needed to meet its stated objective.",
                               "target", "applied/practice", [prerequisite_id], 1, topic)
            units = [prerequisite, target]
        else:
            units = []
            previous = []
            for index, (stage, label) in enumerate(cls.FULL_STAGES):
                uid = "unit_" + hashlib.sha256((topic + f"|{index}|{stage}").encode()).hexdigest()[:12]
                title = f"{label}: {topic}"
                unit = cls._unit(uid, title,
                                 f"A subject-neutral curriculum unit for {topic}; scope is refined using objectives and evidence, not keyword-only search.",
                                 stage, stage, previous, index, topic)
                units.append(unit)
                previous = [uid]
        for left, right in zip(units, units[1:]):
            left["next_units"] = [right["unit_id"]]
        return units

    def create(self, topic, scope="full", source_request="", domain="general"):
        topic = _clean(topic)
        if not topic:
            raise ValueError("topic is required")
        scope = "narrow" if scope == "narrow" else "full"
        mid = self._stable_id(topic, scope)
        now = _now()
        with self._tx() as state:
            old = next((m for m in state["missions"] if m.get("mission_id") == mid), None)
            if old:
                old["updated_at"] = now
                if old.get("status") == "paused": old["status"] = "active"
                return dict(old)
            units = self.build_curriculum(topic, scope)
            mission = {
                "mission_id": mid, "title": topic, "normalized_topic": _key(topic),
                "requested_scope": scope, "target_level": "advanced" if scope == "full" else "focused",
                "current_level": units[0]["level"], "domain": str(domain or "general"), "language": "fa",
                "status": "active", "created_at": now, "updated_at": now,
                "source_request": str(source_request), "curriculum_version": 1,
                "progress_percent": 0.0, "mastery_score": 0.0, "completed_units": [],
                "current_unit": units[0]["unit_id"], "weak_units": [], "blocked_units": [],
                "prerequisite_graph": {u["unit_id"]: list(u["prerequisites"]) for u in units},
                "learning_objectives": [objective for u in units for objective in u["objectives"]],
                "assessment_history": [], "evidence_history": [], "candidate_history": [],
                "approved_learning_ids": [], "next_action": "prepare_lesson",
                "resume_checkpoint": units[0]["unit_id"], "units": units,
                "scheduler_turns": 0,
            }
            state["missions"].append(mission)
            state["scheduler"]["last_mission_id"] = state["scheduler"].get("last_mission_id")
            return dict(mission)

    def get(self, mission_id):
        state = self._validate(load_critical_json(self.path, self._default()))
        row = next((m for m in state["missions"] if m.get("mission_id") == str(mission_id)), None)
        return dict(row) if row else None

    def list(self, include_paused=True):
        state = self._validate(load_critical_json(self.path, self._default()))
        rows = [dict(m) for m in state["missions"] if include_paused or m.get("status") != "paused"]
        return rows

    def find(self, topic):
        key = _key(topic)
        rows = self.list()
        if not key:
            active = [m for m in rows if m.get("status") in ACTIVE_STATUSES]
            return active[-1] if active else (rows[-1] if rows else None)
        exact = [m for m in rows if m.get("normalized_topic") == key or _key(m.get("title")) == key]
        if exact:
            return exact[-1]
        matches = [m for m in rows if key in m.get("normalized_topic", "") or m.get("normalized_topic", "") in key]
        return max(matches, key=lambda m: len(m.get("normalized_topic", ""))) if matches else None

    def _mutate(self, mission_id, fn):
        with self._tx() as state:
            mission = next((m for m in state["missions"] if m.get("mission_id") == str(mission_id)), None)
            if mission is None: return None
            result = fn(mission, state)
            mission["updated_at"] = _now()
            return result if result is not None else dict(mission)

    def pause(self, mission_id):
        return self._mutate(mission_id, lambda m, s: m.update(status="paused", next_action="resume"))

    def resume(self, mission_id):
        def apply(m, s):
            if m.get("status") == "paused":
                m["status"] = "active"
                m["current_unit"] = m.get("resume_checkpoint") or m.get("current_unit")
                m["next_action"] = "resume_checkpoint"
            return dict(m)
        return self._mutate(mission_id, apply)

    def lesson(self, mission_id, unit_id=None):
        mission = self.get(mission_id)
        if not mission: return None
        unit_id = unit_id or mission.get("current_unit")
        unit = next((u for u in mission["units"] if u["unit_id"] == unit_id), None)
        if not unit: return None
        if not self._prerequisites_passed(mission, unit):
            return {"ok": False, "reason": "prerequisite_missing", "missing": [p for p in unit["prerequisites"] if not self._unit_passed(mission, p)]}
        return {
            "lesson_id": "lesson_" + hashlib.sha256((mission_id + unit_id).encode()).hexdigest()[:16],
            "mission_id": mission_id, "unit_id": unit_id,
            "objective": unit["objectives"][0],
            "explanation": f"درس این بخش: {unit['description']} هدف آن {unit['expected_knowledge']} و مهارت قابل‌سنجش آن {unit['expected_skill']}",
            "examples": [f"نمونهٔ راهنما دربارهٔ {unit['title']}: توضیح یک مورد، سپس بیان دلیل و محدودیت آن."],
            "practice": unit["practice_requirements"],
            "assessment": unit["assessment_requirements"],
            "expected_effect": unit["expected_skill"], "evidence": [], "status": "ready_for_practice",
        }

    def search_query(self, mission_id, unit_id=None):
        """Produce a disambiguated evidence query from the active unit, not title alone."""
        mission = self.get(mission_id)
        if not mission: return ""
        unit_id = unit_id or mission.get("current_unit")
        unit = next((u for u in mission.get("units", []) if u.get("unit_id") == unit_id), None)
        if not unit: return ""
        lookup = {u["unit_id"]: u for u in mission.get("units", [])}
        prerequisites = [lookup[p]["title"] for p in unit.get("prerequisites", []) if p in lookup]
        parts = [mission.get("title", ""), unit.get("title", ""), *unit.get("concepts", []),
                 *unit.get("objectives", []), unit.get("expected_knowledge", ""),
                 unit.get("expected_skill", ""), *prerequisites]
        return " ".join(dict.fromkeys(_clean(x) for x in parts if _clean(x)))

    @staticmethod
    def _unit_passed(mission, unit_id):
        unit = next((u for u in mission.get("units", []) if u.get("unit_id") == unit_id), None)
        return bool(unit and unit.get("status") == "mastered")

    @classmethod
    def _prerequisites_passed(cls, mission, unit):
        return all(cls._unit_passed(mission, p) for p in unit.get("prerequisites", []))

    def record_assessment(self, mission_id, unit_id, score, evidence, practice_result=None, transfer_success=False, weak_concepts=None):
        score = max(0.0, min(1.0, float(score)))
        evidence = _clean(evidence)
        if not evidence: return {"ok": False, "reason": "evidence_required"}
        def apply(m, state):
            unit = next((u for u in m["units"] if u["unit_id"] == unit_id), None)
            if unit is None: return {"ok": False, "reason": "unit_not_found"}
            missing = [p for p in unit["prerequisites"] if not self._unit_passed(m, p)]
            if missing: return {"ok": False, "reason": "prerequisite_missing", "missing": missing}
            passed = score >= float(unit.get("mastery_threshold", .8)) and bool(transfer_success or unit.get("stage") in {"foundation", "basic"})
            row = {"assessment_id": "assessment_" + hashlib.sha256((mission_id + unit_id + evidence + str(score)).encode()).hexdigest()[:16],
                   "unit_id": unit_id, "score": score, "passed": passed, "evidence": evidence,
                   "practice_result": str(practice_result or ""), "transfer_success": bool(transfer_success),
                   "weak_concepts": list(weak_concepts or []), "at": _now()}
            if any(x.get("assessment_id") == row["assessment_id"] for x in m["assessment_history"]):
                return {"ok": True, "duplicate": True, "assessment": row, "unit": dict(unit)}
            m["assessment_history"].append(row)
            unit["assessment_history"].append(row)
            unit["attempts"] += 1
            unit["mastery_score"] = max(float(unit.get("mastery_score", 0)), score if passed else min(score, .79))
            unit["weak_concepts"] = list(weak_concepts or []) if not passed else []
            unit["transfer_success"] = bool(transfer_success)
            unit["evidence_history"].append({"evidence": evidence, "at": row["at"], "source": "learner_assessment"})
            m["evidence_history"].append({"unit_id": unit_id, "evidence": evidence, "at": row["at"]})
            if passed:
                unit["pass_count"] += 1
                unit["status"] = "candidate_pending"
                m["status"] = "waiting_for_reviewer"
                m["next_action"] = "review_candidate"
            else:
                unit["fail_count"] += 1
                unit["remediation_count"] += 1
                unit["status"] = "remediation"
                m["weak_units"] = list(dict.fromkeys(m.get("weak_units", []) + [unit_id]))
                m["status"] = "practicing"
                m["next_action"] = "remediate_and_reassess"
            m["resume_checkpoint"] = unit_id
            self._refresh_progress(m)
            return {"ok": True, "assessment": row, "unit": dict(unit), "remediation": not passed}
        return self._mutate(mission_id, apply)

    @staticmethod
    def _refresh_progress(mission):
        units = mission.get("units", [])
        mastered = [u for u in units if u.get("status") == "mastered"]
        mission["completed_units"] = [u["unit_id"] for u in mastered]
        mission["progress_percent"] = round(100 * len(mastered) / max(1, len(units)), 1)
        mission["mastery_score"] = round(sum(float(u.get("mastery_score", 0)) for u in mastered) / max(1, len(units)), 3)
        pending = [u for u in units if u.get("status") != "mastered" and all(LearningMissionManager._unit_passed(mission, p) for p in u.get("prerequisites", []))]
        mission["current_unit"] = pending[0]["unit_id"] if pending else None
        mission["current_level"] = pending[0]["level"] if pending else "completed"
        if not pending:
            mission["status"] = "completed"
            mission["next_action"] = "completed"

    def mark_candidate(self, mission_id, unit_id, candidate_id):
        def apply(m, state):
            unit = next((u for u in m["units"] if u["unit_id"] == unit_id), None)
            if unit is None: return None
            if candidate_id not in unit["candidate_history"]:
                unit["candidate_history"].append(candidate_id)
                m["candidate_history"].append({"candidate_id": candidate_id, "unit_id": unit_id, "status": "waiting_for_reviewer", "at": _now()})
            unit["status"] = "waiting_for_reviewer"
            m["status"] = "waiting_for_reviewer"
            m["next_action"] = "wait_for_reviewer"
            return dict(m)
        return self._mutate(mission_id, apply)

    def mark_review(self, mission_id, unit_id, candidate_id, decision, reason="", source="reviewer"):
        def apply(m, state):
            unit = next((u for u in m["units"] if u["unit_id"] == unit_id), None)
            if unit is None: return None
            for item in m["candidate_history"]:
                if item.get("candidate_id") == candidate_id:
                    if source == "reviewer":
                        item.update(status="human_pending" if decision == "learn" else "rejected",
                                     reviewer_decision=decision, reviewer_reason=str(reason))
                    else:
                        item.update(status="rejected", human_decision="rejected", human_reason=str(reason))
            if decision == "learn":
                unit["status"] = "waiting_for_human"; m["status"] = "waiting_for_human"; m["next_action"] = "human_review"
            else:
                unit["status"] = "remediation"; m["status"] = "active"; m["next_action"] = "revise_candidate_or_remediate"
                unit["weak_concepts"] = list(dict.fromkeys(unit.get("weak_concepts", []) + ["reviewer_rejected_candidate"]))
            return dict(m)
        return self._mutate(mission_id, apply)

    def mark_approved(self, mission_id, unit_id, candidate_id, gate_id, learned_id=None,
                      approval_source="explicit_human"):
        def apply(m, state):
            unit = next((u for u in m["units"] if u["unit_id"] == unit_id), None)
            if unit is None: return None
            if candidate_id not in unit["approved_learning_ids"]:
                unit["approved_learning_ids"].append(candidate_id)
            if gate_id not in m["approved_learning_ids"]:
                m["approved_learning_ids"].append(gate_id)
            unit["status"] = "mastered"
            unit["effect_status"] = "awaiting_future_observation"
            history = unit.get("assessment_history") or []
            latest_score = float(history[-1].get("score", 0)) if history else 0.0
            unit["mastery_score"] = max(float(unit.get("mastery_score", 0)), latest_score)
            for item in m["candidate_history"]:
                if item.get("candidate_id") == candidate_id:
                    item.update(status="approved", gate_proposal_id=gate_id, learned_object_id=learned_id,
                                approval_source=str(approval_source)[:64], human_decision="approved")
            self._refresh_progress(m)
            if m.get("status") != "completed":
                m["status"] = "active"; m["next_action"] = "prepare_lesson"
            return dict(m)
        return self._mutate(mission_id, apply)

    def record_effect(self, mission_id, unit_id, verified, score=0.0, observation=""):
        def apply(m, state):
            unit = next((u for u in m["units"] if u["unit_id"] == unit_id), None)
            if unit is None: return None
            unit["effect_status"] = "effective" if verified and float(score) >= .8 else "weak_effect"
            unit.setdefault("effect_history", []).append({"verified": bool(verified), "score": float(score), "observation": str(observation), "at": _now()})
            if unit["effect_status"] == "weak_effect":
                unit["status"] = "remediation"
                unit["remediation_count"] += 1
                m["weak_units"] = list(dict.fromkeys(m.get("weak_units", []) + [unit_id]))
                m["status"] = "practicing"; m["next_action"] = "effect_remediation"
                self._refresh_progress(m)
            return dict(m)
        return self._mutate(mission_id, apply)

    def next_unit_fair(self):
        with self._tx() as state:
            missions = [m for m in state["missions"] if m.get("status") in {"active", "practicing", "assessing"}]
            if not missions: return None
            last_id = state["scheduler"].get("last_mission_id")
            start = next((i + 1 for i, m in enumerate(missions) if m.get("mission_id") == last_id), 0)
            ordered = missions[start:] + missions[:start]
            # Remediation is prioritized locally; mission rotation remains fair.
            for mission in ordered:
                units = mission.get("units", [])
                candidates = [u for u in units if u.get("status") != "mastered" and self._prerequisites_passed(mission, u)]
                if not candidates: continue
                candidates.sort(key=lambda u: (u.get("status") != "remediation", u.get("order", 0)))
                unit = candidates[0]
                mission["current_unit"] = unit["unit_id"]
                mission["resume_checkpoint"] = unit["unit_id"]
                mission["scheduler_turns"] = int(mission.get("scheduler_turns", 0)) + 1
                mission["updated_at"] = _now()
                state["scheduler"]["last_mission_id"] = mission["mission_id"]
                return {"mission_id": mission["mission_id"], "unit_id": unit["unit_id"], "title": unit["title"]}
            return None

    def status_text(self, mission):
        if not mission: return "مأموریت یادگیری‌ای برای این موضوع پیدا نشد."
        unit = next((u for u in mission.get("units", []) if u["unit_id"] == mission.get("current_unit")), None)
        completed = [u["title"] for u in mission.get("units", []) if u.get("status") == "mastered"]
        weak = [u["title"] for u in mission.get("units", []) if u.get("status") == "remediation" or u.get("weak_concepts")]
        return (f"مأموریت یادگیری: {mission['title']}\nپیشرفت: {mission['progress_percent']}٪\n"
                f"مرحله: {mission.get('current_level', '—')}\nدرس جاری: {unit['title'] if unit else 'تکمیل‌شده'}\n"
                f"درس‌های گذرانده: {', '.join(completed) or 'هنوز هیچ‌کدام'}\n"
                f"نقاط نیازمند تقویت: {', '.join(weak) or 'ندارد'}\nگام بعدی: {mission.get('next_action', '—')}")
