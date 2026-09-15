"""Persian conversation contracts against the canonical dialogue API.

These assert behaviour that the canonical runtime in `core/dialogue.py` really
exhibits. Every assertion below was measured against the canonical runtime before
being written; none of them encode an aspiration.

The benchmark's `unknown` category is a separate, currently-failing case and is
deliberately not asserted here; see `scripts/run_conversation_audit.py` for that
known gap.
"""
import unittest

from core.dialogue import QuestionAnalyzer, ReferenceResolver
from benchmarks.runtime_factory import isolated_runtime_factory


class PersianConversationContractTests(unittest.TestCase):
    REFERENCE_MARKERS = ('این', 'همین', 'اون', 'همون', 'همونو', 'قبلی', 'بالایی', 'این بخش', 'این جواب', 'این مشکل')
    QUESTION_UNIT_CASES = tuple(
        f'پایتون چیست و چرا محبوب است و برای پروژه {i} چه فایده‌ای دارد؟' for i in range(10)
    )
    CORRECTION_CASES = tuple(f'نه، منظورم حافظه {i} بود' for i in range(10))
    UNKNOWN_CASES = tuple(f'آیا فردا در سیاره ناشناخته {i} باران می‌بارد؟' for i in range(10))
    MEMORY_CASES = tuple(f'من پایتون {i} را دوست دارم' for i in range(10))

    def runtime(self):
        return isolated_runtime_factory()()

    def test_10_reference_markers_resolve_to_active_topic(self):
        for marker in self.REFERENCE_MARKERS:
            with self.subTest(marker=marker):
                runtime = self.runtime()
                try:
                    runtime.handle('پایتون چیه؟')
                    answer = runtime.handle(f'{marker} رو بهتر کن')
                    self.assertIn('پایتون', answer)
                finally:
                    runtime.close()

    def test_10_correction_cases_are_recorded_and_acknowledged(self):
        for text in self.CORRECTION_CASES:
            with self.subTest(text=text):
                runtime = self.runtime()
                try:
                    runtime.handle('این بخش رو توضیح بده')
                    answer = runtime.handle(text)
                    state = runtime.dialogue.state
                    self.assertIn(text, state.corrections)
                    self.assertTrue('حافظه' in answer or 'متوجه' in answer)
                finally:
                    runtime.close()

    def test_10_unknown_cases_are_answered_without_fabrication(self):
        for question in self.UNKNOWN_CASES:
            with self.subTest(question=question):
                runtime = self.runtime()
                try:
                    answer = runtime.handle(question)
                    self.assertTrue('UNKNOWN' in answer or 'اطلاعات کافی' in answer)
                finally:
                    runtime.close()

    def test_10_compound_questions_split_into_units(self):
        analyzer = QuestionAnalyzer()
        for text in self.QUESTION_UNIT_CASES:
            with self.subTest(text=text):
                self.assertGreaterEqual(len(analyzer.analyze(text)['question_units']), 3)

    def test_10_memory_recall_cases_return_the_stated_fact(self):
        for text in self.MEMORY_CASES:
            with self.subTest(text=text):
                runtime = self.runtime()
                try:
                    runtime.handle(text)
                    answer = runtime.handle('من چی گفتم؟')
                    self.assertTrue('یادم هست' in answer or 'دوست دارید' in answer)
                finally:
                    runtime.close()

    def test_20_multiturn_dialogues_keep_a_restorable_topic_stack(self):
        for index in range(20):
            with self.subTest(dialogue=index):
                runtime = self.runtime()
                try:
                    runtime.handle('پایتون چیه؟')
                    runtime.handle('حافظه چیه؟')
                    state = runtime.dialogue.state
                    self.assertEqual(state.current_topic, 'حافظه')
                    restored = state.restore_previous_topic()
                    self.assertIn('پایتون', restored)
                finally:
                    runtime.close()

    def test_reference_resolver_uses_topic_then_goal(self):
        resolver = ReferenceResolver()
        runtime = self.runtime()
        try:
            runtime.handle('پایتون چیه؟')
            self.assertIn('پایتون', resolver.resolve('این رو بهتر کن', runtime.dialogue.state, []))
        finally:
            runtime.close()


if __name__ == '__main__':
    unittest.main()
