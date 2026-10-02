"""IRAN Phase 2 — real Soar cognitive foundation acceptance.

These tests use IranRuntime/CognitiveSystem and the official soar-sml runtime.
Mock-only acceptance is intentionally insufficient.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime
from core.soar_cognitive_engine import SoarCognitiveEngine

SRC=Path(__file__).resolve().parents[1]


class SoarCognitiveFoundationAcceptance(unittest.TestCase):
    def runtime(self):
        root=Path(tempfile.mkdtemp(prefix="iran_soar_phase2_"))
        shutil.copy(SRC/"config.json",root/"config.json")
        shutil.copytree(SRC/"data",root/"data")
        shutil.copytree(SRC/"cognitive",root/"cognitive")
        (root/"logs").mkdir(exist_ok=True)
        for name in (
            "conversation_state.json","conversation_events.json","context_tracker.json",
            "soar-test.db","soar_epmem.sqlite","learning_proposals.json"
        ):
            (root/"data"/name).unlink(missing_ok=True)
        cfg=json.loads((root/"config.json").read_text(encoding="utf-8-sig"))
        cfg["memory"]["db"]="data/soar-test.db"
        cfg["runtime"]["event_log"]="logs/events.jsonl"
        cfg["runtime"]["goals"]="data/goals.json"
        (root/"config.json").write_text(json.dumps(cfg,ensure_ascii=False),encoding="utf-8")
        return IranRuntime(root)

    def test_real_soar_runtime_initialized_under_one_brain(self):
        r=self.runtime()
        try:
            status=r.cognitive_system.cognitive_engine.status()
            self.assertTrue(status["available"],status)
            self.assertTrue(status["real_soar"],status)
            self.assertEqual(status["backend"],"soar-sml")
            self.assertTrue(status["rules_loaded"])
            self.assertEqual(status["decision_owner"],"CognitiveSystem")
            arch=r.cognitive_system.architecture_contract()
            self.assertEqual(arch["decision_owner"],"CognitiveSystem")
            self.assertFalse(arch["parallel_decision_paths"])
            self.assertIn("SoarCognitiveEngine",arch["reasoning"])
        finally:r.close()

    def test_phase1_semantics_populate_working_memory_and_run_decision_cycle(self):
        r=self.runtime()
        try:
            answer=r.handle("من روی پروژه‌ای به اسم اهورا کار می‌کنم که برای مدیریت کتاب است.")
            self.assertTrue(str(answer).strip())
            cycle=r.cognitive_system.pipeline.last_cognitive_cycle
            self.assertIsNotNone(cycle)
            self.assertTrue(cycle.real_soar,cycle.to_dict())
            self.assertGreaterEqual(cycle.cycle_count,1,cycle.to_dict())
            self.assertGreaterEqual(cycle.working_memory.get("semantic_fact_count",0),1)
            self.assertTrue(cycle.proposed_operators)
            self.assertTrue(cycle.selected_operator or cycle.impasse,cycle.to_dict())
            self.assertTrue(cycle.semantic_memory_used,cycle.to_dict())
            trace=r.dialogue.last_semantic_trace["cognitive_cycle"]
            self.assertTrue(trace["real_soar"])
        finally:r.close()

    def test_true_soar_tie_impasse_creates_observable_substate(self):
        r=self.runtime()
        try:
            si=r.cognitive_system.pipeline.semantic_intelligence
            slots=r.cognitive_system.pipeline.conversation_foundation.current_state().get("slots",{})
            turn=si.analyze("اسم پروژه ناشناخته چی بود؟",slots=slots,source_turn=1)
            cycle=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"planning","goal":"resolve missing project identity"})
            self.assertTrue(cycle.real_soar,cycle.to_dict())
            self.assertGreaterEqual(len(cycle.proposed_operators),2,cycle.to_dict())
            self.assertTrue(cycle.impasse,cycle.to_dict())
            self.assertIn(cycle.status,{"IMPASSE","RESOLVED_IMPASSE"})
            self.assertTrue(cycle.substate)
            self.assertTrue(any(x.get("stage")=="impasse" for x in cycle.trace))
            self.assertTrue(any(x.get("stage")=="substate-problem-solving" for x in cycle.trace))
            if cycle.status=="RESOLVED_IMPASSE":
                self.assertTrue(cycle.selected_operator)
                self.assertTrue(cycle.substate.get("returned_to_superstate",True))
            self.assertEqual(cycle.goal["subgoals"][0]["status"],"blocked")
        finally:r.close()

    def test_semantic_and_episodic_memory_are_used_without_replacing_iran_memory(self):
        r=self.runtime()
        root=r.root
        try:
            r.handle("من روی پروژه‌ای به اسم سروش کار می‌کنم که برای تحلیل متن است.")
            cycle=r.cognitive_system.pipeline.last_cognitive_cycle
            self.assertTrue(cycle.semantic_memory_used,cycle.to_dict())
            self.assertTrue(cycle.episodic_memory_used,cycle.to_dict())
            rows=r.memory.search(cycle.goal["description"],20,kind="soar_episode")
            self.assertTrue(rows)
            self.assertEqual(
                r.cognitive_system.cognitive_engine.status()["semantic_memory"]["policy"],
                "derived_cache")
        finally:r.close()
        self.assertTrue((root/"data"/"soar_epmem.sqlite").exists())

    def test_goal_hierarchy_and_intermediate_state_are_bounded(self):
        r=self.runtime()
        try:
            si=r.cognitive_system.pipeline.semantic_intelligence
            turn=si.analyze("یک هدف ساختاریافته",slots={},source_turn=1)
            cycle=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"planning","goal":"prepare release candidate"})
            sub=cycle.goal["subgoals"]
            self.assertGreaterEqual(len(sub),4)
            self.assertLessEqual(len(sub),8)
            self.assertIn(sub[0]["status"],{"completed","blocked","failed"})
            self.assertLessEqual(cycle.cycle_count,r.cognitive_system.cognitive_engine.MAX_CYCLES)
            self.assertLess(cycle.elapsed_ms,5000)
        finally:r.close()

    def test_verified_problem_solving_creates_governed_chunk_candidate_only(self):
        r=self.runtime()
        try:
            si=r.cognitive_system.pipeline.semantic_intelligence
            turn=si.analyze("اسم پروژه نامعلوم چی بود؟",slots={},source_turn=1)
            cycle=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"planning","goal":"resolve governed ambiguity"})
            proposal=r.cognitive_system.cognitive_engine.propose_learning(
                cycle,verified=True,outcome="verified problem solving")
            self.assertIsNotNone(proposal)
            self.assertEqual(proposal["kind"],"soar.chunk_candidate")
            self.assertEqual(proposal["status"],"pending")
            self.assertFalse(cycle.working_memory.get("learning_authorized",False))

            # Test harness models an explicit governance approval, then the next
            # matching Soar cycle may expose learning-authorized=yes.
            r.learning_gate.decide(proposal["proposal_id"],"approved")
            cycle2=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"planning","goal":"resolve governed ambiguity"})
            self.assertTrue(cycle2.working_memory.get("learning_authorized"),cycle2.to_dict())
        finally:r.close()

    def test_rl_reward_is_never_self_awarded(self):
        r=self.runtime()
        try:
            si=r.cognitive_system.pipeline.semantic_intelligence
            turn=si.analyze("یک مسئله",slots={},source_turn=1)
            cycle=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"general","goal":"bounded reward test"})
            self.assertIsNone(r.cognitive_system.cognitive_engine.propose_rl_reward(
                cycle,1.0,"self_reward",verified=True))
            self.assertIsNone(r.cognitive_system.cognitive_engine.propose_rl_reward(
                cycle,1.0,"verified_action_outcome",verified=False))
            proposal=r.cognitive_system.cognitive_engine.propose_rl_reward(
                cycle,.5,"test_harness",verified=True)
            self.assertIsNotNone(proposal)
            self.assertEqual(proposal["status"],"pending")
            self.assertEqual(proposal["kind"],"soar.rl_reward_candidate")
        finally:r.close()

    def test_soar_never_executes_jarvis_directly(self):
        r=self.runtime()
        try:
            engine=r.cognitive_system.cognitive_engine
            self.assertFalse(hasattr(engine,"execute_tool"))
            self.assertFalse(hasattr(engine,"computer_use"))
            self.assertEqual(engine.status()["decision_owner"],"CognitiveSystem")
            decision=r.cognitive_system.decide_computer_action(
                "get system information",{},remaining_steps=1)
            self.assertIn(decision.get("status"),{"act","safe_stop","goal_complete"})
        finally:r.close()

    def test_jarvis_dispatch_requires_real_soar_operator_then_cognitive_authority(self):
        r=self.runtime()
        try:
            calls=[]
            original=r.computer_use.execute
            def fake_execute(goal,tool,args):
                calls.append((goal,tool,args))
                return {"success":True,"verification":{"reason":"test-harness","verified":True}}
            r.computer_use.execute=fake_execute
            answer=r.handle("open notepad")
            self.assertEqual(answer,"انجام شد.")
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0][1],"open_application")
            cycle=r.cognitive_system.pipeline.last_cognitive_cycle
            self.assertIsNotNone(cycle)
            self.assertTrue(cycle.real_soar,cycle.to_dict())
            self.assertEqual(cycle.selected_operator,"open_application",cycle.to_dict())
            self.assertEqual(r.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
            self.assertFalse(hasattr(r.cognitive_system.cognitive_engine,"execute_tool"))
            r.computer_use.execute=original
        finally:r.close()

    def test_unknown_and_conflicting_state_are_not_promoted_to_truth(self):
        r=self.runtime()
        try:
            si=r.cognitive_system.pipeline.semantic_intelligence
            unknown=si.analyze("اسم پروژه‌ای که هرگز نگفتم چیست؟",slots={},source_turn=1)
            cycle=r.cognitive_system.cognitive_engine.cycle(
                unknown,r.dialogue.state,parsed={"intent":"question","goal":"resolve absent fact"})
            self.assertIn(cycle.uncertainty,{"unknown","uncertain"})
            self.assertNotEqual(cycle.status,"COMPLETED")
            # Contradictory durable facts stay visible to existing IRAN memory;
            # Soar receives structured state but never declares either value true.
            with r.learning_gate.bypass():
                r.memory.add_semantic_fact("project:x","runtime","3.12",.9,"source-a")
                r.memory.add_semantic_fact("project:x","runtime","3.14",.95,"source-b")
            turn=si.analyze("نسخه runtime پروژه x چیست؟",slots={},source_turn=2)
            cycle2=r.cognitive_system.cognitive_engine.cycle(
                turn,r.dialogue.state,parsed={"intent":"question","goal":"compare conflicting runtime evidence"})
            self.assertTrue(cycle2.real_soar)
            self.assertIn(cycle2.uncertainty,{"unknown","conflicting","inferred"})
            self.assertEqual(r.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
        finally:r.close()

    def test_explicit_observable_fallback_if_real_soar_cannot_initialize(self):
        r=self.runtime()
        try:
            broken=Path(tempfile.mkdtemp(prefix="iran_soar_fallback_"))
            (broken/"data").mkdir()
            engine=SoarCognitiveEngine(
                broken,r.memory,learning_gate=r.learning_gate,event_log=r.events)
            try:
                status=engine.status()
                self.assertFalse(status["real_soar"])
                self.assertEqual(status["backend"],"fallback")
                self.assertTrue(status["init_error"])
                self.assertEqual(status["decision_owner"],"CognitiveSystem")
            finally:engine.close()
        finally:r.close()

    def test_repeated_runtime_lifecycle_uses_real_soar_without_native_teardown_crash(self):
        # This regression used to crash the entire Python process in the SML
        # native binding during runtime.close().
        for _ in range(3):
            r=self.runtime()
            self.assertTrue(r.cognitive_system.cognitive_engine.status()["real_soar"])
            r.handle("یک چرخه شناختی کوتاه اجرا کن.")
            r.close()

    def test_soar_episode_is_not_a_conversation_topic_but_remains_retrievable(self):
        r=self.runtime()
        try:
            r.handle("پایتون چیه؟")
            first=r.conversation_snapshot().get("current_topic","")
            r.handle("Django چیه؟")
            second=r.conversation_snapshot().get("current_topic","")
            self.assertNotEqual(first,second)
            self.assertFalse(str(second).lstrip().startswith("{"),second)
            generic=r.memory.search("Django",20)
            self.assertFalse(any(row[0]=="soar_episode" for row in generic),generic)
            episodes=r.memory.search("Django",20,kind="soar_episode")
            self.assertTrue(episodes)
        finally:r.close()

    def test_restart_preserves_native_epmem_and_iran_episode_bridge(self):
        r=self.runtime(); root=r.root
        try:
            r.handle("من روی پروژه‌ای به اسم پویان کار می‌کنم.")
            self.assertTrue(r.cognitive_system.cognitive_engine.status()["real_soar"])
        finally:r.close()
        self.assertTrue((root/"data"/"soar_epmem.sqlite").exists())
        r2=IranRuntime(root)
        try:
            status=r2.cognitive_system.cognitive_engine.status()
            self.assertTrue(status["real_soar"],status)
            rows=r2.memory.search("پویان",20,kind="soar_episode")
            self.assertTrue(rows)
            self.assertEqual(r2.cognitive_system.architecture_contract()["decision_owner"],"CognitiveSystem")
        finally:r2.close()


if __name__=="__main__":
    unittest.main()

# Final Phase 2 validation v7 marker: native epmem backup persistence.
