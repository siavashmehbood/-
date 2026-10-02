"""Official Soar SML integration for IRAN Phase 2.

CognitiveSystem remains the only public brain/final authority. This module owns
an internal Soar kernel/agent used for bounded cognitive state, operator cycles,
impasse/substate signalling, Soar semantic/episodic memory, and governed
procedural-learning candidates.

No subprocesses are used. The integration uses the official soar-sml Python
bindings and SML API. When Soar is unavailable, fallback is explicit and
observable; IRAN continues through its existing canonical reasoning path.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
import hashlib
import json
import time


@dataclass
class CognitiveOperator:
    name: str
    kind: str = "cognitive"
    confidence: float = 0.5
    expected_effect: str = ""
    requires_authorization: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class CognitiveGoal:
    goal_id: str
    description: str
    status: str = "active"
    subgoals: list[dict] = field(default_factory=list)
    depth: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class SoarCycleResult:
    available: bool
    real_soar: bool
    backend: str
    status: str
    goal: dict = field(default_factory=dict)
    working_memory: dict = field(default_factory=dict)
    proposed_operators: list[dict] = field(default_factory=list)
    selected_operator: str = ""
    impasse: bool = False
    substate: dict = field(default_factory=dict)
    semantic_memory_used: bool = False
    episodic_memory_used: bool = False
    retrieved_semantic: list[dict] = field(default_factory=list)
    retrieved_episodes: list[dict] = field(default_factory=list)
    uncertainty: str = "unknown"
    cycle_count: int = 0
    elapsed_ms: float = 0.0
    fallback_reason: str = ""
    safe_abort: bool = False
    repeated_state: bool = False
    trace: list[dict] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class SoarCognitiveEngine:
    """Bounded internal Soar cognitive engine subordinate to CognitiveSystem."""

    MAX_CYCLES = 8
    MAX_DEPTH = 4
    TIMEOUT_MS = 750

    def __init__(self, root, memory, learning_gate=None, event_log=None):
        self.root = Path(root)
        self.memory = memory
        self.learning_gate = learning_gate
        self.events = event_log
        self.kernel = None
        self.agent = None
        self.sml = None
        self.available = False
        self.real_soar = False
        self.backend = "fallback"
        self.init_error = ""
        self.input_root = None
        self.started_at = time.perf_counter()
        self._last_cycle = None
        self._state_fingerprints = []
        self.rules_path = self.root / "cognitive" / "iran_phase2.soar"
        self.epmem_path = self.root / "data" / "soar_epmem.sqlite"
        self._initialize()
        self.init_elapsed_ms = round((time.perf_counter()-self.started_at)*1000, 3)

    def _emit(self, name, payload):
        try:
            if self.events is not None:
                self.events.emit(name, payload)
        except Exception:
            pass

    def _initialize(self):
        try:
            try:
                import soar_sml as sml
            except Exception:
                import Python_sml_ClientInterface as sml
            self.sml = sml
            # The Python 9.6.5 binding is substantially safer for repeated
            # in-process runtime construction when the kernel shares the caller
            # thread: no SML kernel/event thread needs to be torn down between
            # short-lived IRAN runtimes. IRAN does not attach the Soar debugger,
            # so external-command polling is not required in the cognition path.
            create_current=getattr(sml.Kernel,"CreateKernelInCurrentThread",None)
            kernel = create_current() if callable(create_current) else sml.Kernel.CreateKernelInNewThread()
            if kernel is None:
                raise RuntimeError("soar_kernel_none")
            if hasattr(kernel, "HadError") and kernel.HadError():
                raise RuntimeError(str(kernel.GetLastErrorDescription()))
            agent = kernel.CreateAgent("iran-cognitive-engine")
            if agent is None:
                raise RuntimeError("soar_agent_none")
            if hasattr(kernel, "HadError") and kernel.HadError():
                raise RuntimeError(str(kernel.GetLastErrorDescription()))
            self.kernel = kernel
            self.agent = agent
            loaded = False
            if self.rules_path.exists():
                if hasattr(agent, "LoadProductions"):
                    loaded = bool(agent.LoadProductions(str(self.rules_path)))
                if not loaded:
                    result = str(agent.ExecuteCommandLine(f"source {self._cli_symbol(self.rules_path)}"))
                    loaded = not self._agent_error() and "error" not in result.lower()
            if not loaded:
                raise RuntimeError("soar_productions_not_loaded")

            # IRAN Memory is authoritative durable semantic memory. Soar SMEM is
            # a derived cognitive cache. EPMEM is file-backed to preserve native
            # cognitive episodes across restart.
            self._cmd("smem --set learning on")
            self._cmd("smem --set database memory")
            self._cmd("epmem --set learning on")
            self._cmd("epmem --set trigger dc")
            self._cmd("epmem --set phase selection")
            self._cmd("epmem --set database file")
            self._cmd(f"epmem --set path {self._cli_symbol(self.epmem_path)}")
            self._cmd("epmem --set append on")
            self._cmd("epmem --init")
            # Native chunking is enabled only in states explicitly force-learned
            # by the governed production in iran_phase2.soar.
            self._cmd("chunk only")
            self._cmd("chunk max-chunks 8")
            self.available = True
            self.real_soar = True
            self.backend = "soar-sml"
            self._emit("soar_initialized", {
                "backend": self.backend, "real_soar": True,
                "rules": str(self.rules_path.name),
                "decision_owner": "CognitiveSystem",
            })
        except Exception as exc:
            self.init_error = f"{type(exc).__name__}:{exc}"
            self.available = False
            self.real_soar = False
            self.backend = "fallback"
            self._emit("soar_fallback", {
                "error": self.init_error, "decision_owner": "CognitiveSystem",
                "observable": True,
            })

    def _agent_error(self):
        return bool(self.agent is not None and hasattr(self.agent, "HadError") and self.agent.HadError())

    @staticmethod
    def _cli_symbol(value):
        text = str(value).replace("\\", "/").replace("|", "_")
        return f"|{text}|"

    def _cmd(self, command):
        if self.agent is None:
            return ""
        result = str(self.agent.ExecuteCommandLine(str(command)))
        if self._agent_error():
            raise RuntimeError(str(self.agent.GetLastErrorDescription()))
        return result

    def _create_id(self, parent, attr):
        if hasattr(self.agent, "CreateIdWME"):
            return self.agent.CreateIdWME(parent, str(attr))
        return parent.CreateIdWME(str(attr))

    def _create_string(self, parent, attr, value):
        if hasattr(self.agent, "CreateStringWME"):
            return self.agent.CreateStringWME(parent, str(attr), str(value))
        return parent.CreateStringWME(str(attr), str(value))

    def _create_int(self, parent, attr, value):
        if hasattr(self.agent, "CreateIntWME"):
            return self.agent.CreateIntWME(parent, str(attr), int(value))
        return parent.CreateIntWME(str(attr), int(value))

    def _clear_input(self):
        if self.input_root is None or self.agent is None:
            return
        try:
            if hasattr(self.agent, "DestroyWME"):
                self.agent.DestroyWME(self.input_root)
            elif hasattr(self.input_root, "DestroyWME"):
                self.input_root.DestroyWME()
        except Exception:
            pass
        self.input_root = None

    @staticmethod
    def _semantic_fact_dicts(semantic_turn):
        out = []
        for fact in list(getattr(semantic_turn, "facts", []) or []):
            if hasattr(fact, "to_memory"):
                row = fact.to_memory()
            elif hasattr(fact, "__dict__"):
                row = dict(fact.__dict__)
            elif isinstance(fact, dict):
                row = dict(fact)
            else:
                continue
            out.append(row)
        return out

    @staticmethod
    def _semantic_evidence_dicts(semantic_turn):
        rows = []
        for ev in list(getattr(semantic_turn, "evidence", []) or []):
            if hasattr(ev, "to_dict"):
                rows.append(ev.to_dict())
            elif hasattr(ev, "__dict__"):
                rows.append(dict(ev.__dict__))
            elif isinstance(ev, dict):
                rows.append(dict(ev))
        return rows

    def _goal(self, semantic_turn, state, parsed=None):
        parsed = parsed or {}
        description = str(parsed.get("goal") or getattr(getattr(semantic_turn, "linguistic", None), "normalized_text", "") or "cognitive-turn")
        digest = hashlib.sha1(description.encode("utf-8")).hexdigest()[:12]
        intent = str(parsed.get("intent") or "general").lower()
        if intent in {"build", "planning", "plan", "debug", "action", "tool"}:
            titles = ["understand", "retrieve-evidence", "evaluate-options", "act-or-answer", "verify"]
        elif getattr(semantic_turn, "query", None) and getattr(semantic_turn.query, "relation", ""):
            titles = ["resolve-reference", "retrieve-evidence", "evaluate-consistency", "answer", "verify"]
        else:
            titles = ["understand", "reason", "answer", "verify"]
        subgoals = [{"id": i+1, "title": title, "status": "pending"} for i, title in enumerate(titles)]
        return CognitiveGoal(f"goal:{digest}", description, "active", subgoals, 0)

    def _operators(self, semantic_turn, parsed=None, tool_candidate=None):
        parsed = parsed or {}
        evidence = self._semantic_evidence_dicts(semantic_turn)
        query = getattr(semantic_turn, "query", None)
        relation = str(getattr(query, "relation", "") or "")
        utterance_type = str(getattr(semantic_turn, "utterance_type", "statement") or "statement")
        operators = []
        if tool_candidate:
            operators.append(CognitiveOperator(
                str(tool_candidate), "action", .86, "observable tool result", True))
        if relation and evidence:
            operators.append(CognitiveOperator("answer-from-evidence", "reasoning", .92, "grounded answer"))
        elif relation and not evidence:
            operators.append(CognitiveOperator("retrieve-semantic-memory", "memory", .88, "additional evidence"))
        if utterance_type in {"uncertain", "speculation"}:
            operators.append(CognitiveOperator("preserve-uncertainty", "reasoning", .90, "calibrated uncertainty"))
        intent = str(parsed.get("intent") or "general").lower()
        if intent in {"build", "planning", "plan", "debug"}:
            operators.append(CognitiveOperator("decompose-goal", "planning", .84, "subgoal stack"))
        if not operators:
            operators.append(CognitiveOperator("continue-reasoning", "reasoning", .72, "reasoning state update"))
        return operators[:4]

    def _memory_retrievals(self, goal, semantic_turn):
        semantic = []
        episodes = []
        try:
            semantic = list(self.memory.semantic_search(goal.description, 6))
        except Exception:
            semantic = []
        try:
            episodes = [
                {"kind": row[0], "content": row[1], "created_at": row[2]}
                for row in self.memory.search(goal.description, 6, kind="soar_episode")
            ]
        except Exception:
            episodes = []
        return semantic, episodes

    def _sync_smem(self, facts):
        if not self.real_soar:
            return False
        used = False
        for fact in facts[:12]:
            subject = self._cli_symbol(fact.get("subject", "unknown"))
            relation = self._cli_symbol(fact.get("predicate", fact.get("relation", "related")))
            value = self._cli_symbol(fact.get("object", fact.get("value", "")))
            if value == "||":
                continue
            try:
                self._cmd(f"smem --add {{(<f> ^subject {subject} ^relation {relation} ^value {value})}}")
                used = True
            except Exception:
                continue
        return used

    def _approved_chunk(self, goal):
        if self.learning_gate is None:
            return False
        try:
            for row in self.learning_gate.history(200):
                if row.get("kind") != "soar.chunk_candidate" or row.get("status") != "approved":
                    continue
                payload = row.get("payload") or {}
                if payload.get("goal_id") == goal.goal_id:
                    return True
        except Exception:
            return False
        return False

    def _populate_working_memory(self, semantic_turn, state, goal, operators, semantic_rows, episode_rows, approved_learning=False):
        if not self.real_soar:
            return {}
        self._clear_input()
        il = self.agent.GetInputLink()
        root = self._create_id(il, "iran")
        self.input_root = root
        self._create_string(root, "goal-id", goal.goal_id)
        self._create_string(root, "goal", goal.description[:500])
        self._create_string(root, "goal-status", goal.status)
        self._create_string(root, "learning-authorized", "yes" if approved_learning else "no")
        self._create_string(root, "uncertainty", self._uncertainty(semantic_turn))
        self._create_int(root, "semantic-fact-count", len(self._semantic_fact_dicts(semantic_turn)))
        self._create_int(root, "semantic-evidence-count", len(self._semantic_evidence_dicts(semantic_turn)))
        self._create_int(root, "retrieved-semantic-count", len(semantic_rows))
        self._create_int(root, "retrieved-episode-count", len(episode_rows))
        active_goal = str(getattr(state, "active_goal", "") or "")
        if active_goal:
            self._create_string(root, "active-goal", active_goal[:500])
        self._create_string(root, "current-task", goal.description[:500])
        self._create_string(root, "reasoning-state", "candidate-selection")
        for constraint in list(getattr(state, "remembered_constraints", []) or [])[:12]:
            node=self._create_id(root,"constraint")
            self._create_string(node,"value",str(constraint)[:500])
        for ent in list(getattr(getattr(semantic_turn,"linguistic",None),"entities",[]) or [])[:16]:
            node=self._create_id(root,"entity")
            self._create_string(node,"id",str(getattr(ent,"entity_id","")))
            self._create_string(node,"type",str(getattr(ent,"entity_type","")))
            self._create_string(node,"text",str(getattr(ent,"text",""))[:300])
        for fact in self._semantic_fact_dicts(semantic_turn)[:16]:
            node=self._create_id(root,"semantic-fact")
            self._create_string(node,"subject",str(fact.get("subject",""))[:300])
            self._create_string(node,"relation",str(fact.get("predicate",fact.get("relation","")))[:200])
            self._create_string(node,"value",str(fact.get("object",fact.get("value","")))[:500])
            self._create_string(node,"provenance",str(fact.get("source",fact.get("provenance","")))[:300])
        for ev in self._semantic_evidence_dicts(semantic_turn)[:12]:
            node=self._create_id(root,"evidence")
            self._create_string(node,"subject",str(ev.get("subject",""))[:300])
            self._create_string(node,"relation",str(ev.get("relation",""))[:200])
            self._create_string(node,"value",str(ev.get("value",""))[:500])
            self._create_string(node,"provenance",str(ev.get("provenance",""))[:300])
        for index, op in enumerate(operators):
            node = self._create_id(root, "candidate")
            self._create_string(node, "name", op.name)
            self._create_string(node, "kind", op.kind)
            self._create_string(node, "eligible", "yes")
            self._create_int(node, "order", index + 1)
        for sub in goal.subgoals[:12]:
            node = self._create_id(root, "subgoal")
            self._create_string(node, "name", sub["title"])
            self._create_string(node, "status", sub["status"])
            self._create_int(node, "order", sub["id"])
        self.agent.Commit()
        return {
            "goal_id": goal.goal_id,
            "active_goal": active_goal,
            "semantic_fact_count": len(self._semantic_fact_dicts(semantic_turn)),
            "semantic_evidence_count": len(self._semantic_evidence_dicts(semantic_turn)),
            "retrieved_semantic_count": len(semantic_rows),
            "retrieved_episode_count": len(episode_rows),
            "candidate_actions": [x.to_dict() for x in operators],
            "subgoals": list(goal.subgoals),
            "learning_authorized": bool(approved_learning),
        }

    @staticmethod
    def _uncertainty(semantic_turn):
        if getattr(semantic_turn, "utterance_type", "") in {"uncertain", "speculation"}:
            return "uncertain"
        evidence = list(getattr(semantic_turn, "evidence", []) or [])
        if not evidence and getattr(getattr(semantic_turn, "query", None), "relation", ""):
            return "unknown"
        active = [x for x in evidence if not bool(getattr(x, "superseded", False))]
        values = {str(getattr(x, "value", "")) for x in active}
        if len(values) > 1:
            return "conflicting"
        return "known" if active else "inferred"

    def _read_commands(self):
        selected = ""
        impasse = False
        substate = {}
        if self.agent is None:
            return selected, impasse, substate
        try:
            count = int(self.agent.GetNumberCommands())
        except Exception:
            count = 0
        for i in range(count):
            try:
                cmd = self.agent.GetCommand(i)
                name = str(cmd.GetCommandName())
                if name == "decision":
                    selected = str(cmd.GetParameterValue("operator") or "")
                elif name == "impasse":
                    impasse = True
                    substate = {
                        "status": str(cmd.GetParameterValue("status") or "tie"),
                        "resolution": str(cmd.GetParameterValue("resolution") or "retrieve-evidence"),
                    }
                if hasattr(cmd, "AddStatusComplete"):
                    cmd.AddStatusComplete()
            except Exception:
                continue
        return selected, impasse, substate

    def _record_episode(self, result):
        payload = {
            "goal": result.goal,
            "operator": result.selected_operator,
            "impasse": result.impasse,
            "status": result.status,
            "uncertainty": result.uncertainty,
            "semantic_memory_used": result.semantic_memory_used,
            "episodic_memory_used": result.episodic_memory_used,
            "time": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            self.memory.add("soar_episode", json.dumps(payload, ensure_ascii=False, sort_keys=True),
                            .78, confidence=.82, source="soar_epmem_bridge")
        except Exception:
            pass

    def cycle(self, semantic_turn, state, parsed=None, tool_candidate=None):
        started = time.perf_counter()
        goal = self._goal(semantic_turn, state, parsed)
        operators = self._operators(semantic_turn, parsed, tool_candidate)
        semantic_rows, episode_rows = self._memory_retrievals(goal, semantic_turn)
        facts = self._semantic_fact_dicts(semantic_turn)
        semantic_used = self._sync_smem(facts) if self.real_soar else False
        approved = self._approved_chunk(goal)
        wm = {}
        trace = [{"stage": "semantic-input", "facts": len(facts), "goal": goal.goal_id}]
        selected = ""
        impasse = False
        substate = {}
        cycle_count = 0
        safe_abort = False
        repeated = False

        if self.real_soar:
            try:
                wm = self._populate_working_memory(
                    semantic_turn, state, goal, operators, semantic_rows, episode_rows, approved)
                trace.append({"stage": "working-memory-update", "candidate_count": len(operators)})
                fingerprint = hashlib.sha1(json.dumps(wm, sort_keys=True, default=str).encode()).hexdigest()
                if fingerprint in self._state_fingerprints[-3:]:
                    repeated = True
                self._state_fingerprints.append(fingerprint)
                self._state_fingerprints = self._state_fingerprints[-8:]
                if repeated:
                    safe_abort = True
                else:
                    deadline = time.perf_counter() + self.TIMEOUT_MS / 1000.0
                    while cycle_count < self.MAX_CYCLES and time.perf_counter() < deadline:
                        cycle_count += 1
                        self.agent.RunSelf(1)
                        selected, impasse, substate = self._read_commands()
                        if selected or impasse:
                            break
                if impasse:
                    trace.append({"stage": "impasse", "substate": dict(substate)})
                    # Bounded substate problem solving: use the already-structured
                    # candidate/evidence state to choose a preferred candidate,
                    # feed that preference back through the official Soar input
                    # link, and let Soar's decision procedure resolve the tie.
                    if operators and self.input_root is not None:
                        preferred=max(operators,key=lambda op:float(op.confidence))
                        self._create_string(self.input_root,"preferred",preferred.name)
                        self.agent.Commit()
                        trace.append({
                            "stage":"substate-problem-solving",
                            "preferred":preferred.name,
                            "basis":"candidate-confidence+retrieved-evidence",
                            "semantic_hits":len(semantic_rows),
                            "episodic_hits":len(episode_rows),
                        })
                        for _ in range(3):
                            if cycle_count >= self.MAX_CYCLES:
                                break
                            cycle_count += 1
                            self.agent.RunSelf(1)
                            selected2, _impasse2, substate2 = self._read_commands()
                            if selected2:
                                selected=selected2
                                substate.update(substate2 or {})
                                substate["resolved"]=True
                                substate["result"]=selected2
                                trace.append({
                                    "stage":"substate-result",
                                    "operator":selected2,
                                    "returned_to_superstate":True,
                                })
                                break
                if selected:
                    trace.append({"stage": "operator-selected", "operator": selected})
                if not selected and not impasse and not safe_abort:
                    safe_abort = True
            except Exception as exc:
                safe_abort = True
                self.init_error = f"cycle:{type(exc).__name__}:{exc}"
        else:
            selected = operators[0].name if operators else ""
            trace.append({"stage": "fallback", "reason": self.init_error})

        status = ("RESOLVED_IMPASSE" if impasse and selected else
                  "IMPASSE" if impasse else
                  "ABORTED" if safe_abort else
                  "SELECTED" if selected else "UNRESOLVED")
        if goal.subgoals:
            if impasse:
                goal.subgoals[0]["status"]="blocked"
            elif selected:
                goal.subgoals[0]["status"]="completed"
                if len(goal.subgoals)>1:
                    goal.subgoals[1]["status"]="active"
            elif safe_abort:
                goal.subgoals[0]["status"]="failed"
        trace.append({"stage":"intermediate-state","subgoals":[dict(x) for x in goal.subgoals]})
        result = SoarCycleResult(
            available=self.available, real_soar=self.real_soar, backend=self.backend,
            status=status, goal=goal.to_dict(), working_memory=wm,
            proposed_operators=[x.to_dict() for x in operators],
            selected_operator=selected, impasse=impasse, substate=substate,
            semantic_memory_used=semantic_used,
            episodic_memory_used=bool(self.real_soar and cycle_count > 0),
            retrieved_semantic=semantic_rows[:6], retrieved_episodes=episode_rows[:6],
            uncertainty=self._uncertainty(semantic_turn), cycle_count=cycle_count,
            elapsed_ms=round((time.perf_counter()-started)*1000, 3),
            fallback_reason=self.init_error if not self.real_soar else "",
            safe_abort=safe_abort, repeated_state=repeated, trace=trace,
        )
        self._last_cycle = result
        self._record_episode(result)
        self._emit("soar_cycle", {
            "real_soar": result.real_soar, "status": result.status,
            "selected_operator": result.selected_operator, "impasse": result.impasse,
            "cycle_count": result.cycle_count, "elapsed_ms": result.elapsed_ms,
            "decision_owner": "CognitiveSystem",
        })
        return result

    def propose_learning(self, cycle_result, verified=False, outcome=""):
        """Create governed candidates only; never apply durable learning directly."""
        if self.learning_gate is None or not verified or not cycle_result:
            return None
        payload = {
            "goal_id": (cycle_result.goal or {}).get("goal_id", ""),
            "goal": (cycle_result.goal or {}).get("description", ""),
            "operator": cycle_result.selected_operator,
            "impasse": bool(cycle_result.impasse),
            "outcome": str(outcome)[:1000],
            "source": "verified_cognitive_outcome",
            "real_soar": bool(cycle_result.real_soar),
        }
        return self.learning_gate.request(
            "soar.chunk_candidate", payload,
            f"Soar governed chunk candidate: {payload['goal'][:160]}")

    def propose_rl_reward(self, cycle_result, reward, source, verified=False):
        """RL preference changes are staged, never self-applied."""
        allowed = {"verified_action_outcome", "explicit_user_feedback", "test_harness"}
        if not verified or source not in allowed or self.learning_gate is None:
            return None
        value = max(-1.0, min(1.0, float(reward)))
        return self.learning_gate.request(
            "soar.rl_reward_candidate",
            {
                "goal_id": (cycle_result.goal or {}).get("goal_id", ""),
                "operator": cycle_result.selected_operator,
                "reward": value,
                "source": source,
                "verified": True,
            },
            "Controlled Soar operator reward candidate")

    def status(self):
        return {
            "available": self.available,
            "real_soar": self.real_soar,
            "backend": self.backend,
            "init_error": self.init_error,
            "rules_loaded": bool(self.real_soar and self.rules_path.exists()),
            "working_memory": bool(self.real_soar and self.agent is not None),
            "semantic_memory": {"enabled": bool(self.real_soar), "policy": "derived_cache"},
            "episodic_memory": {
                "enabled": bool(self.real_soar),
                "persistent_path": str(self.epmem_path),
                "exists": self.epmem_path.exists(),
            },
            "chunking": {"mode": "only", "governance": "LearningGate"},
            "rl": {"durable_rewards": "LearningGate_only"},
            "decision_owner": "CognitiveSystem",
            "init_elapsed_ms": getattr(self, "init_elapsed_ms", 0.0),
            "limits": {"max_cycles": self.MAX_CYCLES, "max_depth": self.MAX_DEPTH, "timeout_ms": self.TIMEOUT_MS},
            "last_cycle": self._last_cycle.to_dict() if self._last_cycle else {},
        }

    def close(self):
        """Shutdown the SML kernel exactly once.

        SML owns Agent lifetime. Kernel.Shutdown() destroys its agents; calling
        DestroyAgent first can double-release native objects in the Python
        bindings and has caused process-level segmentation faults in regression
        teardown.
        """
        try:
            self._clear_input()
        except Exception:
            pass
        kernel=self.kernel
        self.agent=None
        self.kernel=None
        try:
            if kernel is not None and hasattr(kernel, "Shutdown"):
                kernel.Shutdown()
        except Exception:
            pass
