"""Integrated offline cognitive controller for IRAN.

Clean-room synthesis of proven cognitive-architecture ideas: Soar-style
production control, LIDA-style attention/global workspace, and procedural
learning. No models, embeddings, APIs, or external services are used.
"""
from dataclasses import dataclass, field
import json
from pathlib import Path
from time import time


@dataclass
class WorkspaceItem:
    content: str
    source: str
    salience: float
    confidence: float
    kind: str = "evidence"
    timestamp: float = field(default_factory=time)

    @property
    def activation(self):
        age = max(0.0, time() - self.timestamp)
        decay = 1.0 / (1.0 + age / 30.0)
        return max(0.0, min(1.0, self.salience * self.confidence * decay))


@dataclass
class Procedure:
    name: str
    intent: str
    steps: list
    successes: int = 0
    failures: int = 0
    value: float = 0.5
    uses: int = 0

    @property
    def reliability(self):
        total = self.successes + self.failures
        return self.value if total == 0 else self.successes / total


@dataclass
class SelfState:
    cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    last_intent: str = ""
    capabilities: dict = field(default_factory=dict)
    limits: list = field(default_factory=list)


class GlobalWorkspace:
    """Small broadcast workspace: only the most activated items become global."""
    def __init__(self, capacity=64, broadcast_limit=8):
        self.capacity = int(capacity)
        self.broadcast_limit = int(broadcast_limit)
        self.items = []
        self.broadcast = []

    def clear_turn(self):
        self.items = self.items[-8:]
        self.broadcast = []

    def add(self, content, source, salience=.5, confidence=.5, kind="evidence"):
        item = WorkspaceItem(str(content), str(source), float(salience), float(confidence), str(kind))
        self.items.append(item)
        self.items = self.items[-self.capacity:]
        return item

    def attend(self, query=""):
        q = str(query).lower().split()
        ranked = []
        for item in self.items:
            lexical = sum(1 for token in q if token and token in item.content.lower()) / max(1, len(q))
            ranked.append((item.activation + .20 * lexical, item))
        ranked.sort(key=lambda x: x[0], reverse=True)
        self.broadcast = [item for _, item in ranked[:self.broadcast_limit]]
        return self.broadcast

    def snapshot(self):
        return {"items": len(self.items), "broadcast": [x.content for x in self.broadcast]}


class ProceduralLearner:
    """Error-driven local procedure memory with reinforcement and decay."""
    def __init__(self, path=None, capacity=512):
        self.path = Path(path) if path else None
        self.capacity = int(capacity)
        self.procedures = {}
        self._load()

    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.procedures = {k: Procedure(**v) for k, v in raw.items()}
        except Exception:
            self.procedures = {}

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: vars(v) for k, v in self.procedures.items()}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _key(intent, steps):
        return intent + "::" + "|".join(map(str, steps))

    def record(self, intent, steps, success, reward=0.0):
        steps = [str(x) for x in steps if str(x).strip()]
        if not steps:
            return None
        key = self._key(str(intent), steps)
        proc = self.procedures.get(key)
        if proc is None:
            proc = Procedure(key, str(intent), steps)
            self.procedures[key] = proc
        proc.uses += 1
        if success:
            proc.successes += 1
            proc.value = min(.99, proc.value + .10 + .10 * max(0.0, float(reward)))
        else:
            proc.failures += 1
            proc.value = max(.01, proc.value - .12)
        if len(self.procedures) > self.capacity:
            weakest = min(self.procedures, key=lambda k: (self.procedures[k].uses, self.procedures[k].value))
            self.procedures.pop(weakest, None)
        self._save()
        return proc

    def best(self, intent):
        rows = [p for p in self.procedures.values() if p.intent == str(intent)]
        return max(rows, key=lambda p: (p.reliability, p.value, p.uses), default=None)

    def snapshot(self):
        return {"count": len(self.procedures), "procedures": [vars(x) for x in self.procedures.values()]}


class CognitiveController:
    """Central controller joining attention, production selection and learning."""
    def __init__(self, runtime, procedure_path=None):
        self.runtime = runtime
        self.workspace = GlobalWorkspace()
        self.procedures = ProceduralLearner(procedure_path)
        self.self_model = SelfState()
        self.last_cycle = {}
        self.cycle_id = 0

    def _capabilities(self):
        return {
            "symbolic_reasoning": hasattr(self.runtime, "nars"),
            "knowledge_graph": hasattr(self.runtime, "knowledge"),
            "typed_atomspace": hasattr(self.runtime, "atomspace"),
            "working_memory": hasattr(self.runtime, "cognitive_core"),
            "planning": hasattr(self.runtime, "planner") or hasattr(self.runtime, "cognitive_core"),
            "procedural_learning": True,
            "offline": True,
        }

    def perceive(self, text, state=None):
        self.workspace.clear_turn()
        self.workspace.add(text, "perception", .95, 1.0, "input")
        if state is not None:
            for evidence in getattr(state, "evidence", [])[:12]:
                self.workspace.add(evidence.get("content", ""), evidence.get("source", "memory"),
                                   .65, evidence.get("confidence", .5), evidence.get("kind", "evidence"))
            for item in getattr(state, "contradictions", [])[:4]:
                self.workspace.add(str(item), "contradiction", .9, .8, "conflict")
        return self.workspace.attend(text)

    def choose(self, state):
        intent = getattr(state, "intent", "general")
        procedure = self.procedures.best(intent)
        candidates = []
        if procedure:
            candidates.append({"action": "execute_procedure", "score": procedure.reliability + .15, "procedure": procedure})
        if getattr(state, "contradictions", None):
            candidates.append({"action": "resolve_contradiction", "score": .86})
        if getattr(state, "evidence", None):
            candidates.append({"action": "answer_with_evidence", "score": .82})
        candidates.append({"action": "clarify_or_retrieve", "score": .55})
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]

    def cycle(self, text, state, answer=None):
        self.cycle_id += 1
        self.self_model.cycles += 1
        self.self_model.last_intent = getattr(state, "intent", "general")
        self.self_model.capabilities = self._capabilities()
        attended = self.perceive(text, state)
        selected = self.choose(state)
        verified = bool(answer and str(answer).strip())
        score = float(getattr(state, "confidence", .5))
        self.last_cycle = {
            "cycle": self.cycle_id,
            "attention": [x.content for x in attended],
            "selected": selected["action"],
            "selection_score": round(selected["score"], 4),
            "goal": getattr(state, "goal", ""),
            "intent": getattr(state, "intent", "general"),
            "verified": verified,
            "confidence": score,
        }
        return self.last_cycle

    def learn(self, state, answer, verification):
        score = float(verification.get("score", 0.0))
        success = bool(verification.get("passed"))
        if success:
            self.self_model.successful_cycles += 1
        else:
            self.self_model.failed_cycles += 1
            if "verification" not in self.self_model.limits:
                self.self_model.limits.append("verification")
        steps = getattr(state, "plan", []) or ["understand", "respond", "verify"]
        proc = self.procedures.record(getattr(state, "intent", "general"), steps, success, score)
        if proc:
            self.workspace.add(proc.name, "procedural_memory", .7, proc.reliability, "learned_procedure")
        return proc

    def snapshot(self):
        return {"cycle": self.last_cycle, "workspace": self.workspace.snapshot(),
                "self_model": vars(self.self_model).copy(), "procedural": self.procedures.snapshot()}
