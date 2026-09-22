import tempfile, unittest
from pathlib import Path
from learning.input_fabric import InputFabric

class InputFabricTests(unittest.TestCase):
    def test_dedupe(self):
        with tempfile.TemporaryDirectory() as d:
            f=InputFabric(Path(d))
            a=f.ingest("پایتون یک زبان است.")
            b=f.ingest("  پایتون   یک زبان است.  ")
            self.assertFalse(a["duplicate"]); self.assertTrue(b["duplicate"])
            self.assertEqual(f.stats()["events"],1)
    def test_code_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            f=InputFabric(Path(d))
            r=f.ingest("def add(a,b):\n return a+b",source="document",input_type="code")
            self.assertIn("procedure_candidate",{x["kind"] for x in r["units"]})
    def test_batch_domains(self):
        with tempfile.TemporaryDirectory() as d:
            f=InputFabric(Path(d))
            r=f.ingest_batch([
              {"content":"حل معادله و احتمال در ریاضی","source":"document","input_type":"document"},
              {"content":"Python function loop","source":"web","input_type":"web_page"},
              {"content":"اصلاح کن: پاسخ قبلی اشتباه است","source":"feedback","input_type":"correction"}])
            self.assertEqual(r["new"],3)
            self.assertEqual(f.stats()["domains"]["mathematics"],1)
            self.assertEqual(f.stats()["domains"]["programming"],1)

if __name__=="__main__": unittest.main()


def test_long_input_duplicate_survives_restart(tmp_path):
    from learning.input_fabric import InputFabric
    content = 'متن طولانی ' * 4000
    fabric = InputFabric(tmp_path)
    first = fabric.ingest(content)
    assert not first['duplicate']
    restored = InputFabric(tmp_path)
    assert restored.ingest(content)['duplicate']
    assert len(restored.events) == 1


def test_long_inputs_with_same_prefix_remain_distinct(tmp_path):
    from learning.input_fabric import InputFabric
    prefix = 'متن طولانی ' * 4000
    fabric = InputFabric(tmp_path)
    fabric.ingest(prefix + 'اول')
    restored = InputFabric(tmp_path)
    assert not restored.ingest(prefix + 'دوم')['duplicate']
    assert restored.ingest(prefix + 'اول')['duplicate']
