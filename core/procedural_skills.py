"""Deterministic procedural skill memory for IRAN.

Experience becomes a reusable skill only after repeated independently verified
success. Skill reuse checks symbolic preconditions, records transfer distance,
and updates trust from later verified outcomes. No embeddings or external AI.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import json
import re


@dataclass
class Skill:
    name: str
    domain: str
    goal_pattern: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    trust: float = 0.50
    uses: int = 0
    successes: int = 0
    failures: int = 0
    source_experiences: int = 0
    last_verified: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class ProceduralSkillMemory:
    """Promote verified experience into reusable procedures and skills."""

    def __init__(self, path, min_samples=2, min_distinct_goals=2):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.min_samples = int(min_samples)
        self.min_distinct_goals = int(min_distinct_goals)
        self.skills: dict[str, dict] = {}
        self._load()

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"[\w-]+", str(text).lower(), flags=re.UNICODE))

    @classmethod
    def similarity(cls, a, b):
        x, y = cls._tokens(a), cls._tokens(b)
        if not x or not y:
            return 0.0
        return len(x & y) / len(x | y)

    @staticmethod
    def _skill_id(domain, strategy):
        raw = re.sub(r"[^\w-]+", "_", f"{domain}:{strategy}".lower()).strip("_")
        return raw or "general_default"

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.skills = data if isinstance(data, dict) else {}
        except Exception:
            self.skills = {}

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.skills, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _candidate_rows(self, experiences, domain, strategy):
        rows = []
        for row in experiences:
            if not row.get("verified") or float(row.get("score", 0)) < 0.75:
                continue
            if domain and str(row.get("domain", "general")) != str(domain):
                continue
            if str(row.get("strategy", "default")) != str(strategy):
                continue
            rows.append(row)
        return rows

    def promote(self, experiences, domain="general", strategy="default"):
        """Promote repeated verified success into a skill; otherwise do nothing."""
        rows = self._candidate_rows(experiences, domain, strategy)
        goals = {str(r.get("goal", "")).strip() for r in rows if str(r.get("goal", "")).strip()}
        if len(rows) < self.min_samples or len(goals) < self.min_distinct_goals:
            return None
        sid = self._skill_id(domain, strategy)
        actions = [str(r.get("action", "")).strip() for r in rows if str(r.get("action", "")).strip()]
        expected = str(rows[-1].get("expected", ""))
        skill = self.skills.get(sid, asdict(Skill(name=sid, domain=str(domain), goal_pattern=str(next(iter(goals))))))
        skill["steps"] = list(dict.fromkeys(actions))[:8]
        skill["expected"] = expected
        skill["source_experiences"] = len(rows)
        skill["trust"] = round(min(0.98, max(float(skill.get("trust", 0.5)),
            sum(float(r.get("score", 0)) for r in rows) / len(rows))), 3)
        skill["last_verified"] = str(rows[-1].get("timestamp", ""))
        self.skills[sid] = skill
        self._save()
        return dict(skill)

    def retrieve(self, goal, domain=None, limit=5):
        """Retrieve skills by symbolic token overlap, not semantic embeddings."""
        ranked = []
        for sid, skill in self.skills.items():
            if domain and str(skill.get("domain")) != str(domain):
                continue
            sim = self.similarity(goal, skill.get("goal_pattern", ""))
            if sim <= 0:
                continue
            rank = 0.65 * sim + 0.35 * float(skill.get("trust", 0.5))
            ranked.append((rank, sid, skill, sim))
        ranked.sort(key=lambda x: (x[0], x[2].get("trust", 0)), reverse=True)
        return [{**dict(skill), "id": sid, "match": round(sim, 3), "rank": round(rank, 3)}
                for rank, sid, skill, sim in ranked[:int(limit)]]

    def check_preconditions(self, skill, context=None):
        """Return explicit symbolic precondition result before reuse."""
        context = context or {}
        required = list(skill.get("preconditions", []))
        facts = set(str(x).lower() for x in context.get("facts", []))
        missing = [p for p in required if str(p).lower() not in facts]
        return {"ready": not missing, "required": required, "missing": missing}

    def prepare_transfer(self, goal, context=None, domain=None):
        candidates = self.retrieve(goal, domain=domain, limit=5)
        usable = []
        rejected = []
        for skill in candidates:
            checks = self.check_preconditions(skill, context)
            if checks["ready"]:
                usable.append({"skill": skill, "preconditions": checks, "transfer": "symbolic"})
            else:
                rejected.append({"skill": skill.get("id"), "preconditions": checks})
        return {"candidates": usable, "rejected": rejected}

    def observe(self, skill_id, verified, score=0.0):
        """Update trust only from an independently verified reuse outcome."""
        skill = self.skills.get(str(skill_id))
        if skill is None:
            return None
        skill["uses"] = int(skill.get("uses", 0)) + 1
        if verified and float(score) >= 0.75:
            skill["successes"] = int(skill.get("successes", 0)) + 1
            skill["trust"] = round(min(0.99, float(skill.get("trust", 0.5)) + 0.04), 3)
        else:
            skill["failures"] = int(skill.get("failures", 0)) + 1
            skill["trust"] = round(max(0.05, float(skill.get("trust", 0.5)) - 0.08), 3)
        skill["last_verified"] = datetime.now().isoformat(timespec="seconds")
        self._save()
        return dict(skill)

    def stats(self):
        return {
            "skills": len(self.skills),
            "uses": sum(int(s.get("uses", 0)) for s in self.skills.values()),
            "successes": sum(int(s.get("successes", 0)) for s in self.skills.values()),
            "failures": sum(int(s.get("failures", 0)) for s in self.skills.values()),
        }
