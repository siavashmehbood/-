"""User-facing answer hygiene contracts.

The project requires that internal analysis never appear in the answer shown to the
user. Two canonical sites broke that rule by describing the pipeline in the reply:

  * `AnswerRepair.repair` echoed the question back as a quoted "remaining part" and
    then announced its own evidence policy.
  * a chat layer appended the last line of the rejected answer to a follow-up, which
    was often that same internal notice.

A user asking a follow-up saw meta-commentary about "the remaining part of the
question" instead of an answer. No test covered it, so it survived.

These tests drive the real runtime and assert no pipeline vocabulary reaches output.
They are deliberately written against behaviour (the response for a given turn
sequence), not against a template string, so the wording can improve without
weakening the guarantee.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime

# Phrases that only make sense as internal pipeline description. If any of these
# reaches a user, the honesty and answer-hygiene contracts have been broken.
INTERNAL_PIPELINE_MARKERS = (
    'بخش باقی‌مانده',
    'باقی‌مانده سؤال',
    'شواهد کافی ندارم',
    'question_units',
    'evidence_not_used',
    'too_generic',
    'verification.status',
    'CLARIFY',
    'REPAIR',
    'این بخش شواهد',
)


class AnswerHygieneTests(unittest.TestCase):
    def make_runtime(self):
        tmp = Path(tempfile.mkdtemp())
        cfg = json.loads(Path('config.json').read_text(encoding='utf-8-sig'))
        cfg['memory']['db'] = 'data/test.db'
        cfg['runtime']['event_log'] = 'logs/test.jsonl'
        cfg['runtime']['goals'] = 'data/goals.json'
        (tmp / 'config.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
        (tmp / 'data').mkdir()
        (tmp / 'logs').mkdir()
        return IranRuntime(tmp)

    def assertNoInternalLeak(self, answer, context):
        for marker in INTERNAL_PIPELINE_MARKERS:
            self.assertNotIn(marker, answer, f'internal pipeline wording leaked for {context}: {marker}')

    def test_follow_up_after_unknown_topic_does_not_leak_pipeline(self):
        # Regression: the honest-UNKNOWN turn is followed by "how does it work?",
        # which used to answer with the internal remainder notice.
        runtime = self.make_runtime()
        try:
            runtime.handle('نظارت تصویری چیه؟')
            answer = runtime.handle('چطور کار میکنه؟')
            self.assertNoInternalLeak(answer, 'follow-up after unknown topic')
            self.assertTrue(answer.strip())
        finally:
            runtime.close()

    def test_follow_up_after_known_topic_does_not_leak_pipeline(self):
        runtime = self.make_runtime()
        try:
            runtime.handle('پایتون چیه؟')
            for follow_up in ('چطور کار میکنه؟', 'مثال بزن', 'بیشتر توضیح بده'):
                answer = runtime.handle(follow_up)
                self.assertNoInternalLeak(answer, follow_up)
        finally:
            runtime.close()

    def test_all_benchmark_answers_are_free_of_internal_wording(self):
        from benchmarks.persian_conversation_benchmark import PersianConversationBenchmark
        from benchmarks.runtime_factory import isolated_runtime_factory

        report = PersianConversationBenchmark().run(isolated_runtime_factory())
        for scenario in report.get('results', report.get('scenarios', [])):
            answer = str(scenario.get('answer', ''))
            if answer:
                self.assertNoInternalLeak(answer, scenario.get('name', 'benchmark scenario'))

    def test_unknown_follow_up_still_answers_honestly(self):
        runtime = self.make_runtime()
        try:
            runtime.handle('نظارت تصویری چیه؟')
            answer = runtime.handle('چطور کار میکنه؟')
            # Whatever the wording, the turn must produce a real reply rather than
            # an empty string or a bare internal notice.
            self.assertGreater(len(answer.strip()), 10)
        finally:
            runtime.close()


if __name__ == '__main__':
    unittest.main()
