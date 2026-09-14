import json
import tempfile
import unittest
from pathlib import Path
from runtime.app import IranRuntime


def fa(*xs):
    return ''.join(chr(x) for x in xs)

class UserModelRuntimeTests(unittest.TestCase):
    def make_root(self, tmp):
        root=Path(tmp)
        config=json.loads(Path('config.json').read_text(encoding='utf-8-sig'))
        config['memory']['db']='data/db.sqlite'
        config['runtime']['event_log']='events.jsonl'
        config['runtime']['goals']='goals.json'
        (root/'config.json').write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
        return root

    def test_explicit_creator_fact_persists_and_is_used_after_restart(self):
        statement=fa(1605,1606,32,1587,1575,1586,1606,1583,1607,32,1575,1740,1606,32,1662,1585,1608,1688,1607,32,1607,1587,1578,1605)
        question=fa(1605,1606,32,1670,1607,32,1606,1602,1588,1740,32,1583,1585,32,1662,1585,1608,1688,1607,32,1583,1575,1585,1605,63)
        with tempfile.TemporaryDirectory() as d:
            root=self.make_root(d)
            r=IranRuntime(root)
            r.handle(statement)
            first=r.handle(question)
            self.assertTrue(any(f['predicate']=='role' and f['object']=='creator' for f in r.user_model.facts()))
            r.close()
            r2=IranRuntime(root)
            second=r2.handle(question)
            self.assertTrue(any(f['predicate']=='role' and f['object']=='creator' for f in r2.user_model.facts()))
            self.assertIn('creator', first)
            self.assertIn('creator', second)
            r2.close()

    def test_unstated_identity_is_not_invented(self):
        question=fa(1605,1606,32,1670,1607,32,1606,1602,1588,1740,32,1583,1585,32,1662,1585,1608,1688,1607,32,1583,1575,1585,1605,63)
        with tempfile.TemporaryDirectory() as d:
            r=IranRuntime(self.make_root(d))
            self.assertEqual(r.user_model.facts(), [])
            r.close()

    def test_name_and_creator_are_separate_facts(self):
        statement=fa(1605,1606,32,1587,1740,1575,1608,1588,32,1605,1607,1576,1608,1583,1740,32,1548,32,1587,1575,1586,1606,1583,1607,32,1662,1585,1608,1688,1607,32,1607,1587,1578,1605)
        with tempfile.TemporaryDirectory() as d:
            r=IranRuntime(self.make_root(d))
            r.handle(statement)
            facts=r.user_model.facts(limit=20)
            self.assertTrue(any(f['predicate']=='name' and f['object']=='سیاوش مهبودی' for f in facts))
            self.assertTrue(any(f['predicate']=='role' and f['object']=='creator' for f in facts))
            self.assertFalse(any(f['predicate']=='name' and 'سازنده' in f['object'] for f in facts))
            r.close()

    def test_like_object_drops_persian_ra(self):
        statement=fa(1605,1606,32,1576,1585,1606,1575,1605,1607,32,1606,1608,1740,1587,1740,32,1585,1575,32,1583,1608,1587,1578,32,1583,1575,1585,1605)
        with tempfile.TemporaryDirectory() as d:
            r=IranRuntime(self.make_root(d))
            r.handle(statement)
            facts=r.user_model.facts(limit=20)
            self.assertTrue(any(f['predicate']=='likes' and f['object']=='برنامه نویسی' for f in facts))
            self.assertFalse(any(f['predicate']=='likes' and f['object'].endswith(' را') for f in facts))
            r.close()

if __name__=='__main__': unittest.main()
