from core.dialogue import CognitiveContext, AnswerPlanner

def test_learning_strategy_changes_conversation_plan():
    ctx = CognitiveContext(user_message="سلام", question_units=["سلام"], learning_guidance={"recommended_strategy":"conversation"})
    plan = AnswerPlanner().plan(ctx)
    assert plan.steps[0] == "preserve_conversation_context"

def test_learning_failure_signal_changes_plan():
    ctx = CognitiveContext(user_message="سلام", question_units=["سلام"], learning_guidance={"recommended_strategy":"evidence-first", "failure_signal":True})
    plan = AnswerPlanner().plan(ctx)
    assert plan.steps[0] == "avoid_recent_failed_pattern"
