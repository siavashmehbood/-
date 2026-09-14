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
        self.assertNotIn('حتماً', a)

if __name__ == '__main__': unittest.main()
