import unittest
import json
import tempfile
from pathlib import Path
from runtime.app import IranRuntime

class UnifiedCognitionTests(unittest.TestCase):
    def make_runtime(self):
        d=Path(tempfile.mkdtemp())
        cfg=json.loads(Path('config.json').read_text(encoding='utf-8-sig'))
        cfg['memory']['db']='data/test.db'
        cfg['runtime']['event_log']='logs/test.jsonl'
        cfg['runtime']['goals']='data/goals.json'
        (d/'config.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
        (d/'data').mkdir(); (d/'logs').mkdir()
        return d,IranRuntime(d)

    def test_preference_is_canonical_and_recalled(self):
        d,r=self.make_runtime()
        try:
            self.assertIn('برنامه نویسی',r.handle('من برنامه نویسی را دوست دارم'))
            recalled=r.handle('من چه چیزی درباره خودم بهت گفتم؟')
            self.assertIn('برنامه نویسی',recalled)
            self.assertNotIn('برنامه نویسی را»',recalled)
        finally: r.close()

    def test_reference_uses_previous_goal_not_assistant_scaffold(self):
        d,r=self.make_runtime()
        try:
            r.handle('موضوع اصلی ما معماری شناختی ایران است')
            answer=r.handle('همون قبلی رو ادامه بده')
            self.assertIn('معماری شناختی ایران',answer)
            self.assertNotIn("('assistant'",answer)
        finally: r.close()

    def test_how_question_is_not_split_inside_word(self):
        d,r=self.make_runtime()
        try:
            answer=r.handle('چطور می‌توانی بهتر بفهمی؟')
            self.assertIn('مسیر عملی',answer)
            self.assertIn('حافظه',answer)
        finally: r.close()

if __name__=='__main__': unittest.main()
