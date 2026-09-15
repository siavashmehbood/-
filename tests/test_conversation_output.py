import unittest
from pathlib import Path
import tempfile
from runtime.app import IranRuntime

class ConversationOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        import json
        (self.tmp/'config.json').write_text((Path('config.json')).read_text(encoding='utf-8'), encoding='utf-8')
        cfg=json.loads((self.tmp/'config.json').read_text(encoding='utf-8'))
        cfg['memory']['db']='data/test.db'; cfg['runtime']['event_log']='logs/test.jsonl'; cfg['runtime']['goals']='data/goals.json'
        (self.tmp/'config.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
        (self.tmp/'data').mkdir(); (self.tmp/'logs').mkdir()
        self.r=IranRuntime(self.tmp)
    def tearDown(self): self.r.close()
    def test_basic_output(self):
        a=self.r.handle('سلام')
        self.assertTrue(a and len(a)>3)
    def test_project_identity(self):
        self.r.handle('من سازنده پروژه IRAN هستم')
        self.assertIn('سازنده پروژه IRAN', self.r.handle('من چه چیزی درباره خودم بهت گفتم؟'))
    def test_project_name(self):
        self.assertIn('IRAN', self.r.handle('اسم پروژه چیه؟'))
    def test_purpose(self):
        self.assertIn('معماری شناختی', self.r.handle('چرا ساخته شدی؟'))
    def test_unknown_is_honest(self):
        a=self.r.handle('آیا فردا ساعت ۸ باران می‌بارد؟')
        # The honest refusal must actually be present. Asserting only the absence of
        # a confident word let an unrelated answer (a clock reading) pass this test
        # while the UNKNOWN path was unreachable, which is how the routing defect
        # stayed hidden.
        self.assertIn('UNKNOWN', a)
        self.assertNotIn('حتماً', a)

    def test_unknown_is_honest_for_planet_question(self):
        a=self.r.handle('دمای دقیق هسته مشتری در سال ۱۴۲۰ چند است؟')
        self.assertIn('UNKNOWN', a)

    def test_time_request_still_answers_with_clock(self):
        self.assertIn('زمان سیستم', self.r.handle('ساعت الان چند است'))

if __name__ == '__main__': unittest.main()
