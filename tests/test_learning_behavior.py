from core.dialogue import CognitiveContext, AnswerPlanner

def test_learning_strategy_changes_conversation_plan():
    ctx = CognitiveContext(user_message="سلام", question_units=["سلام"], learning_guidance={"recommended_strategy":"conversation"})
    plan = AnswerPlanner().plan(ctx)
    assert plan.steps[0] == "preserve_conversation_context"

def test_learning_failure_signal_changes_plan():
    ctx = CognitiveContext(user_message="سلام", question_units=["سلام"], learning_guidance={"recommended_strategy":"evidence-first", "failure_signal":True})
    plan = AnswerPlanner().plan(ctx)
    assert plan.steps[0] == "avoid_recent_failed_pattern"

from core.dialogue import AnswerRepair, Verification, AnswerPlan

def test_learning_policy_changes_actual_repair_for_risky_unknown():
    class C: pass
    c=C(); c.learning_guidance={}; c.question_type='what'; c.current_topic='موضوع قبلی'; c.relevant_knowledge=[]; c.uncertainty=.8
    plan=AnswerPlan(['x'], True, 'UNKNOWN', '', [], ['avoid_recent_failed_pattern'], .8)
    v=Verification('PASS', [], [], [], .8)
    out=AnswerRepair().repair(c, 'پاسخ قبلی', v, plan)
    assert out.startswith('UNKNOWN:')

def test_learning_policy_preserves_topic_in_followup_repair():
    class C: pass
    c=C(); c.question_type='follow_up'; c.current_topic='پایتون'; c.relevant_knowledge=[]; c.uncertainty=.2
    plan=AnswerPlan(['x'], True, 'FOLLOW_UP', '', [], ['preserve_conversation_context'], .2)
    v=Verification('PASS', [], [], [], .9)
    out=AnswerRepair().repair(c, 'ادامه می‌دهم.', v, plan)
    assert 'پایتون' in out
