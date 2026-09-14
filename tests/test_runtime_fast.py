import unittest,json
from pathlib import Path
from tempfile import TemporaryDirectory
from runtime.app import IranRuntime

class FastRuntimeTests(unittest.TestCase):
    def test_runtime_and_metrics(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            for d in ('data','logs','sandbox'): (root/d).mkdir()
            cfg={'name':'ایران','version':'test','model':{'provider':'iran'},'memory':{'db':'data/x.db','max_history':6},'security':{'safe_mode':True,'allow_shell':False,'allow_network_tools':True},'self_improvement':{'sandbox':'sandbox'},'runtime':{'event_log':'logs/e.jsonl','goals':'data/g.json'}}
            (root/'config.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
            rt=IranRuntime(root)
            try:
                self.assertIn('سلام 👋 من ایران هستم',rt.handle('سلام'))
                self.assertEqual(rt.decide('ساعت الان')['intent'],'time')
                self.assertGreaterEqual(len(rt.metrics()['events']),1)
            finally:
                rt.close()

if __name__=='__main__': unittest.main()
