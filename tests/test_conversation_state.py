import unittest
from core.conversation_state import ConversationState


class ConversationStateTests(unittest.TestCase):
    def test_reference_resolves_to_current_topic(self):
        state = ConversationState(topic='موتور پاسخ‌گویی')
        self.assertEqual(state.resolve_reference('این چرا سطحی است؟'), 'موتور پاسخ‌گویی')

    def test_follow_up_keeps_topic(self):
        state = ConversationState(topic='حافظه معنایی')
        state.update('چطور بهترش کنیم؟', 'پاسخ')
        self.assertEqual(state.topic, 'حافظه معنایی')
        self.assertEqual(state.referent, 'حافظه معنایی')

    def test_correction_is_recorded(self):
        state = ConversationState(topic='پایتون')
        state.update('نه، منظورم جنگو بود', 'باشه')
        self.assertEqual(state.correction, 'نه، منظورم جنگو بود')
        self.assertIn('نه، منظورم جنگو بود', state.unresolved)

    def test_goal_and_entity_update(self):
        state = ConversationState()
        state.update('برای پروژه ایران یک موتور پاسخ بساز', '',
                     {'goal': 'ساخت موتور پاسخ', 'entities': [{'text': 'پروژه ایران'}]})
        self.assertEqual(state.goal, 'ساخت موتور پاسخ')
        self.assertEqual(state.topic, 'پروژه ایران')


    def test_empty_state(self):
        s = ConversationState()
        self.assertEqual(s.turns, 0)
        self.assertEqual(s.prompt_context(), '')

    def test_turn_counter_increments(self):
        s = ConversationState(); s.update('سلام'); s.update('درباره پروژه بگو')
        self.assertEqual(s.turns, 2)

    def test_last_user_is_normalized(self):
        s = ConversationState(); s.update('  سلام   دنیا  ')
        self.assertEqual(s.last_user, 'سلام دنیا')

    def test_assistant_turn_is_retained(self):
        s = ConversationState(); s.update('پروژه', 'پاسخ آزمایشی')
        self.assertEqual(s.last_assistant, 'پاسخ آزمایشی')

    def test_goal_is_retained(self):
        s = ConversationState(); s.update('ساخت سیستم', parsed={'goal':'ساخت سیستم امن'})
        self.assertEqual(s.goal, 'ساخت سیستم امن')

    def test_entity_becomes_topic(self):
        s = ConversationState(); s.update('درباره حافظه', parsed={'entities':[{'text':'حافظه'}]})
        self.assertEqual(s.topic, 'حافظه')

    def test_reference_uses_goal_when_topic_missing(self):
        s = ConversationState(goal='ساخت سیستم'); self.assertEqual(s.resolve_reference('این را ادامه بده'), 'ساخت سیستم')

    def test_reference_uses_last_user_as_fallback(self):
        s = ConversationState(last_user='بررسی پروژه'); self.assertEqual(s.resolve_reference('همین را انجام بده'), 'بررسی پروژه')

    def test_unresolved_reference_is_empty(self):
        s = ConversationState(); self.assertEqual(s.resolve_reference('این را انجام بده'), '')

    def test_follow_up_preserves_topic(self):
        s = ConversationState(topic='حافظه'); s.update('ادامه بده'); self.assertEqual(s.topic, 'حافظه')

    def test_follow_up_sets_referent(self):
        s = ConversationState(topic='حافظه'); s.update('بیشتر توضیح بده'); self.assertEqual(s.referent, 'حافظه')

    def test_correction_is_recorded(self):
        s = ConversationState(); s.update('نه منظورم حافظه بود')
        self.assertEqual(s.correction, 'نه منظورم حافظه بود')

    def test_correction_is_unresolved(self):
        s = ConversationState(); s.update('اشتباهه')
        self.assertIn('اشتباهه', s.unresolved)

    def test_prompt_context_contains_topic(self):
        s = ConversationState(topic='پروژه'); self.assertIn('current_topic=پروژه', s.prompt_context())

    def test_prompt_context_contains_goal(self):
        s = ConversationState(goal='تست'); self.assertIn('active_goal=تست', s.prompt_context())

    def test_persian_normalization(self):
        s = ConversationState(); s.update('يک كلمه'); self.assertEqual(s.last_user, 'یک کلمه')

    def test_reference_boundary_does_not_match_internet(self):
        s = ConversationState(topic='پروژه'); self.assertEqual(s.resolve_reference('اینترنت لازم است'), '')

if __name__ == '__main__':
    unittest.main()

# conversation regression suite
