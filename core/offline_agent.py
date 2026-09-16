"""Offline symbolic agent substrate inspired by mature cognitive architectures.

This module re-implements compatible capabilities independently: perception,
associative activation, multi-hop inference, impasse/subgoals, skill plasticity,
reward, observation, verification and consolidation. No model or network call.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import math
import re


@dataclass
class SymbolicPercept:
    text: str
    intent: str
    entities: list[str] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    polarity: str = "neutral"
    question: str = "none"
    salience: float = .5


@dataclass
class MemoryNode:
    key: str
    text: str
    activation: float = .5
    importance: float = .5
    uses: int = 0
    last_used: int = 0


@dataclass
class Skill:
    name: str
    intent: str
    action: str
    success: float = .5
    uses: int = 0
    failures: int = 0


@dataclass
class AgentResult:
    percept: dict
    recalled: list = field(default_factory=list)
    inference_chain: list = field(default_factory=list)
    hypotheses: list = field(default_factory=list)
    impasse: dict = field(default_factory=dict)
    subgoals: list = field(default_factory=list)
    plan: list = field(default_factory=list)
    action: str = "respond"
    observation: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    reward: float = 0.0
    learned: list = field(default_factory=list)


class SymbolicPerception:
    """Transparent language-to-structure conversion without an ML model."""
    def __init__(self):
        self.intent_terms = {
            "question": ("چیست", "چی", "چرا", "چگونه", "چطور", "آیا", "کی", "کجا"),
            "build": ("بساز", "ایجاد", "پیاده", "اضافه", "توسعه"),
            "debug": ("خطا", "باگ", "خراب", "کار نمی", "رفع", "اشکال"),
            "inspection": ("بررسی", "چک", "وضعیت", "تحقیق", "ببین"),
            "planning": ("برنامه", "نقشه", "مرحله", "چطور انجام"),
            "memory": ("یادت", "گفتیم", "قبلا", "درباره خودم"),
            "compare": ("مقایسه", "فرق", "تفاوت", "مشابه"),
        }

    def normalize(self, text):
        return re.sub(r"\s+", " ", str(text).strip().replace("ي", "ی").replace("ك", "ک"))

    def perceive(self, text):
        t = self.normalize(text)
        low = t.lower()
        scores = {k: sum(1 for term in v if term in low) for k, v in self.intent_terms.items()}
        intent = max(scores, key=scores.get) if max(scores.values()) else "general"
        words = re.findall(r"[آ-یA-Za-z][آ-یA-Za-z0-9‌_-]*", t)
        stop = {"این", "آن", "یک", "برای", "درباره", "من", "تو", "ما", "را", "به", "از", "در", "که", "و", "با"}
        entities = [w for w in words if len(w) > 2 and w not in stop]
        polarity = "negative" if any(x in low for x in ("نمی", "نیست", "نباید", "بد", "خراب")) else "positive" if any(x in low for x in ("خوب", "عالی", "درست", "موفق")) else "neutral"
        question = "why" if "چرا" in low else "how" if any(x in low for x in ("چطور", "چگونه")) else "yes_no" if "آیا" in low else "what" if any(x in low for x in ("چی", "چیست")) else "none"
        commands = []
        for marker in ("باید", "انجام بده", "بررسی کن", "بساز", "اجرا کن", "اضافه کن"):
            if marker in low:
                commands.append({"marker": marker, "goal": t.split(marker, 1)[1].strip(" :،")})
        relations = self._relations(t, entities)
        salience = min(.98, .35 + .10 * len(entities) + .12 * len(commands) + .12 * (intent != "general"))
        return SymbolicPercept(t, intent, entities[:20], relations, commands, polarity, question, salience)

    def _relations(self, text, entities):
        if len(entities) < 2:
            return []
        relation_words = ("دوست", "دارد", "نیاز", "باعث", "سبب", "وابسته", "مشابه", "مربوط")
        found = next((x for x in relation_words if x in text), None)
        return [{"subject": entities[0], "predicate": found or "related_to", "object": entities[1]}] if found else []


class AssociativeMemory:
    """Local Hebbian-style activation graph with decay and spreading activation."""
    def __init__(self, capacity=256):
        self.capacity = int(capacity)
        self.nodes: dict[str, MemoryNode] = {}
        self.edges: dict[tuple[str, str], float] = {}
        self.tick = 0

    def observe(self, text, importance=.5, key=None):
        self.tick += 1
        key = key or self._key(text)
        node = self.nodes.get(key)
        if node is None:
            node = MemoryNode(key, str(text), .55, float(importance), 0, self.tick)
            self.nodes[key] = node
        node.activation = min(1.0, node.activation + .25)
        node.importance = max(node.importance, float(importance))
        node.uses += 1
        node.last_used = self.tick
        self._trim()
        return node

    def recall(self, query, limit=8):
        q = self._tokens(query)
        scored = []
        for node in self.nodes.values():
            overlap = len(q & self._tokens(node.text)) / max(1, len(q))
            score = .45 * overlap + .25 * node.activation + .20 * node.importance + .10 * min(1, node.uses / 5)
            if overlap or not q:
                scored.append((score, node))
        scored.sort(key=lambda x: (x[0], x[1].last_used), reverse=True)
        out = []
        for score, node in scored[:limit]:
            node.activation = min(1.0, node.activation + .05)
            out.append({"key": node.key, "text": node.text, "score": round(score, 3), "activation": round(node.activation, 3)})
        self._spread(q)
        return out

    def associate(self, a, b, amount=.1):
        if not a or not b or a == b:
            return
        key = (str(a), str(b))
        self.edges[key] = min(1.0, self.edges.get(key, .0) + float(amount))

    def decay(self, rate=.02):
        for node in self.nodes.values():
            node.activation *= max(.0, 1.0 - float(rate))
        for key in list(self.edges):
            self.edges[key] *= max(.0, 1.0 - float(rate) * .5)

    def _spread(self, tokens):
        if not tokens:
            return
        for (a, b), weight in self.edges.items():
            if a in tokens and b in self.nodes:
                self.nodes[b].activation = min(1.0, self.nodes[b].activation + .08 * weight)

    def _trim(self):
        if len(self.nodes) <= self.capacity:
            return
        victim = min(self.nodes.values(), key=lambda n: n.activation * .6 + n.importance * .3 + min(1, n.uses / 10) * .1)
        self.nodes.pop(victim.key, None)

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"[\wآ-ی]+", str(text).lower()))

    @staticmethod
    def _key(text):
        return " ".join(sorted(set(re.findall(r"[\wآ-ی]+", str(text).lower()))))[:160]


class MultiHopReasoner:
    """Deterministic graph traversal for short symbolic inference chains."""
    def infer(self, facts, goal, max_hops=4):
        target = self._tokens(goal)
        current = set(target)
        chain = []
        used = set()
        for hop in range(1, int(max_hops) + 1):
            candidates = []
            for idx, fact in enumerate(facts):
                if idx in used:
                    continue
                text = self._fact_text(fact)
                overlap = len(current & self._tokens(text)) / max(1, len(current))
                if overlap >= .15:
                    candidates.append((overlap, idx, fact, text))
            if not candidates:
                break
            score, idx, fact, text = max(candidates, key=lambda x: x[0])
            used.add(idx)
            chain.append({"hop": hop, "fact": fact, "match": round(score, 3)})
            current |= self._tokens(text)
        return chain

    @staticmethod
    def _fact_text(fact):
        if isinstance(fact, dict):
            return " ".join(str(v) for v in fact.values())
        return str(fact)

    @staticmethod
    def _tokens(text):
        return set(re.findall(r"[\wآ-ی]+", str(text).lower()))


class ImpasseManager:
    """Turns unresolved decisions into explicit symbolic subgoals."""
    def resolve(self, confidence, evidence_count, contradictions, alternatives):
        reasons = []
        if evidence_count == 0:
            reasons.append("no_evidence")
        if contradictions:
            reasons.append("contradiction")
        if alternatives > 1:
            reasons.append("competing_hypotheses")
        if confidence < .60:
            reasons.append("low_confidence")
        active = bool(reasons)
        subgoals = []
        if active:
            if "no_evidence" in reasons: subgoals.append("retrieve_more_evidence")
            if "contradiction" in reasons: subgoals.append("resolve_contradiction")
            if "competing_hypotheses" in reasons: subgoals.append("compare_hypotheses")
            if "low_confidence" in reasons and not subgoals: subgoals.append("increase_confidence")
        return {"active": active, "reasons": reasons, "subgoals": subgoals}


class PlasticSkillRegistry:
    """Small symbolic skill memory with reinforcement and forgetting."""
    def __init__(self):
        self.skills: dict[str, Skill] = {}

    def select(self, intent):
        candidates = [s for s in self.skills.values() if s.intent == intent]
        candidates.sort(key=lambda s: (s.success, s.uses), reverse=True)
        return candidates[0] if candidates else None

    def reinforce(self, intent, action, reward):
        key = f"{intent}|{action}"
        skill = self.skills.get(key)
        if skill is None:
            skill = Skill(key, intent, action)
            self.skills[key] = skill
        old = skill.success
        skill.success = max(.02, min(.98, old * .8 + float(reward) * .2))
        skill.uses += 1
        if reward < .4:
            skill.failures += 1
        return skill

    def decay(self, rate=.01):
        for skill in self.skills.values():
            skill.success = max(.02, skill.success * (1.0 - float(rate)))


class OfflineAgentKernel:
    """Closed symbolic agent cycle; external tools are optional effectors."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.perception = SymbolicPerception()
        self.memory = AssociativeMemory()
        self.reasoner = MultiHopReasoner()
        self.impasse = ImpasseManager()
        self.skills = PlasticSkillRegistry()
        self.cycles = 0
        self.last = None

    def cycle(self, text, answer=None, facts=None, execute=None):
        self.cycles += 1
        percept = self.perception.perceive(text)
        self.memory.observe(percept.text, percept.salience)
        for rel in percept.relations:
            self.memory.observe(rel["subject"], .7, rel["subject"])
            self.memory.observe(rel["object"], .7, rel["object"])
            self.memory.associate(rel["subject"], rel["object"], .12)
        recalled = self.memory.recall(text, 8)
        external = list(facts or [])
        try:
            external.extend(self.runtime.knowledge.query(text, 12))
        except Exception:
            pass
        chain = self.reasoner.infer(external + recalled, percept.text, 4)
        contradictions = self._contradictions(external)
        confidence = min(.98, .35 + .08 * len(recalled) + .10 * len(chain) + .12 * (percept.intent != "general"))
        if contradictions:
            confidence = max(.08, confidence - .18)
        hypothesis_count = 2 if percept.intent == 'compare' else 1
        query_tokens = self.reasoner._tokens(percept.text)
        relevant_external = [f for f in external if len(query_tokens & self.reasoner._tokens(self.reasoner._fact_text(f))) / max(1, len(query_tokens)) >= .12]
        imp = self.impasse.resolve(confidence, len(relevant_external) + len(recalled), contradictions, hypothesis_count)
        skill = self.skills.select(percept.intent)
        persistent_skill = self._persistent_skill(percept.text, percept.intent)
        if persistent_skill and float(persistent_skill.get('confidence', 0.0)) >= .55 and bool(persistent_skill.get('enabled', True)):
            action = str(persistent_skill.get('name') or persistent_skill.get('skill_id') or self._default_action(percept, imp))
        else:
            action = skill.action if skill and skill.success >= .55 else self._default_action(percept, imp)
        plan = self._plan(percept, imp, action)
        observation = {"provided": answer is not None, "non_empty": bool(str(answer or "").strip()), "action": action}
        if execute is not None:
            try:
                observation.update(execute(action) or {})
            except Exception as exc:
                observation.update({"success": False, "error": type(exc).__name__})
        verification = self._verify(percept, answer, confidence, observation)
        reward = self._reward(verification)
        if not verification.get('passed'):
            plan = list(plan) + ['reassess', 'replan', 'verify']
        learned = []
        learned.append(asdict(self.skills.reinforce(percept.intent, action, reward)))
        self._update_persistent_skill(persistent_skill, percept, action, reward)
        self.memory.decay()
        self.skills.decay()
        if reward >= .75:
            self._consolidate(percept, action)
        self._persist_cognitive_trace(percept, action, verification, reward)
        result = AgentResult(asdict(percept), recalled, chain, [{"name": x, "score": round(confidence, 3)} for x in imp["reasons"]], imp, imp["subgoals"], plan, action, observation, verification, reward, learned)
        self.last = result
        return result

    def learn_outcome(self, answer, score):
        """Close the runtime response loop without re-running perception."""
        if not self.last:
            return None
        reward = max(0.0, min(1.0, float(score)))
        action = self.last.action
        intent = self.last.percept.get('intent', 'general')
        skill = self._persistent_skill(self.last.percept.get('text', ''), intent)
        if skill:
            self.runtime.skills.update_outcome(skill.get('skill_id'), reward >= .75)
        elif reward >= .75 and hasattr(self.runtime, 'learn_procedure_skill'):
            try:
                self.runtime.learn_procedure_skill(self.last.percept.get('text', ''), action, domain=intent)
            except Exception:
                pass
        self.last.observation['answer'] = str(answer)[:1000]
        self.last.verification['runtime_score'] = round(reward, 3)
        self.last.reward = reward
        if reward >= .75:
            self._consolidate(self._percept_from_dict(self.last.percept), action)
        return self.last.reward

    @staticmethod
    def _percept_from_dict(data):
        return SymbolicPercept(**data)

    def _persistent_skill(self, goal, intent):
        try:
            rows = self.runtime.skills.retrieve(goal, None, 5)
            return next((r for r in rows if r.get('enabled', True)), None)
        except Exception:
            return None

    def _update_persistent_skill(self, skill, percept, action, reward):
        try:
            if skill:
                self.runtime.skills.update_outcome(skill.get('skill_id'), reward >= .75)
            elif reward >= .75 and hasattr(self.runtime, 'learn_procedure_skill'):
                self.runtime.learn_procedure_skill(percept.text, action, domain=percept.intent)
        except Exception:
            pass

    def _persist_cognitive_trace(self, percept, action, verification, reward):
        payload = {
            'intent': percept.intent, 'action': action, 'reward': round(float(reward), 3),
            'verified': bool(verification.get('passed')), 'question': percept.question,
        }
        try:
            self.runtime.memory.add('offline_agent', payload, max(.45, float(reward)), float(reward), 'offline-agent')
        except Exception:
            pass
        try:
            from memory.semantic import SemanticMemory
            SemanticMemory(self.runtime.memory).consolidate_experience(percept.text, reward, action)
        except Exception:
            pass

    def _default_action(self, percept, imp):
        if imp["active"]:
            return imp["subgoals"][0]
        return {"question": "retrieve_and_answer", "build": "inspect_and_build", "debug": "inspect_and_test", "inspection": "inspect_and_report", "planning": "decompose_and_plan", "memory": "retrieve_and_verify", "compare": "compare_evidence"}.get(percept.intent, "respond")

    def _plan(self, percept, imp, action):
        if imp["active"]:
            return ["understand", *imp["subgoals"], "reassess", "respond"]
        return ["perceive", "retrieve", "reason", action, "observe", "verify", "learn"]

    def _verify(self, percept, answer, confidence, observation):
        text = str(answer or "").strip()
        checks = {"answer_present": bool(text), "intent_known": percept.intent != "general" or bool(text), "observation_valid": bool(observation), "uncertainty_consistent": not (confidence < .4 and len(text) > 600)}
        return {"passed": all(checks.values()), "score": round(sum(checks.values()) / len(checks), 3), "checks": checks, "confidence": round(confidence, 3)}

    @staticmethod
    def _reward(verification):
        return float(verification.get("score", 0.0)) if verification.get("passed") else max(.05, float(verification.get("score", 0.0)) * .5)

    def _consolidate(self, percept, action):
        self.memory.observe(f"skill:{percept.intent}:{action}", .85, f"skill:{percept.intent}:{action}")
        if hasattr(self.runtime, "learning"):
            try:
                self.runtime.learning.record(percept.text, action, "verified-success", .86, percept.intent, action, "offline-agent")
            except Exception:
                pass

    @staticmethod
    def _contradictions(facts):
        out = []
        positive = defaultdict(list)
        negative = defaultdict(list)
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            key = (str(fact.get("subject", "")), str(fact.get("predicate", "")))
            value = str(fact.get("value", fact.get("object", "")))
            target = negative if any(x in value.lower() for x in ("نیست", "نمی", "false", "not")) else positive
            target[key].append(value)
        for key, values in positive.items():
            if key in negative:
                out.append({"key": key, "positive": values, "negative": negative[key]})
        return out

    def snapshot(self):
        return {"cycles": self.cycles, "skills": [asdict(x) for x in self.skills.skills.values()], "memory_nodes": len(self.memory.nodes), "memory_edges": len(self.memory.edges), "last": asdict(self.last) if self.last else None}
