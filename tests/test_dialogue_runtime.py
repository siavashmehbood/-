import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime.app import IranRuntime


class RuntimeDialogueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='iran_dialogue_test_'))
        root = Path('.')
        shutil.copy(root/'config.json', self.tmp/'config.json')
        shutil.copytree(root/'data', self.tmp/'data')
        state = self.tmp/'data'/'conversation_state.json'
        if state.exists():
            state.unlink()
        (self.tmp/'logs').mkdir()
        c = json.loads((self.tmp/'config.json').read_text(encoding='utf-8-sig'))
        c['memory']['db'] = 'data/test.db'
        c['runtime']['event_log'] = 'logs/test.jsonl'
        (self.tmp/'config.json').write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
        self.r = IranRuntime(self.tmp)

    def tearDown(self):
        self.r.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ask(self, text):
        return self.r.handle(text)

    def test_basic_and_followup(self):
        self.assertIn('تهران', self.ask('پایتخت ایران چیه؟'))
        self.assertIn('همان سؤال قبلی', self.ask('چرا؟'))

    def test_python_project_reference(self):
        self.assertIn('پایتون', self.ask('پایتون چیه؟'))
        self.assertIn('پروژه IRAN', self.ask('برای پروژه من خوبه؟'))

    def test_correction(self):
        self.ask('پایتون چیه؟')
        self.ask('این قسمت رو بهتر کن.')
        a = self.ask('نه، منظورم حافظه بود.')
        self.assertIn('حافظه', a)
        self.assertIn('حافظه', self.r.conversation_snapshot()['current_topic'])

    def test_unknown_honesty(self):
        a = self.ask('آب و هوای شیراز چطوره؟')
        self.assertIn('اطلاعات کافی ندارم', a)

    def test_multi_intent(self):
        a = self.ask('پایتون چیه و چرا محبوبه و برای پروژه من چه فایده‌ای داره؟')
        self.assertIn('۱)', a)
        self.assertIn('۲)', a)
        self.assertIn('۳)', a)

    def test_topic_restore(self):
        self.ask('پایتون چیه؟')
        self.ask('حافظه چیه؟')
        a = self.ask('موضوع قبلی رو ادامه بده.')
        self.assertIn('پایتون', a)

    def test_persistent_state(self):
        self.ask('پایتون چیه؟')
        self.r.close()
        r2 = IranRuntime(self.tmp)
        self.assertEqual(r2.conversation_snapshot()['current_topic'], 'پایتون چیه؟')
        r2.close()


if __name__ == '__main__':
    unittest.main()
