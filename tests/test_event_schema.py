import tempfile
import unittest
from pathlib import Path

from runtime.events import EventLog


class EventSchemaTests(unittest.TestCase):
    def test_emit_has_cognitive_trace_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            log = EventLog(Path(directory) / 'events.jsonl')
            turn_id = log.begin_turn('turn-test')
            row = log.emit('reasoning_completed', {'confidence': .8})
            self.assertEqual(row['turn_id'], turn_id)
            self.assertEqual(row['stage'], 'cognition')
            self.assertEqual(row['status'], 'completed')
            self.assertIn('duration_ms', row)
            self.assertEqual(row['data']['confidence'], .8)

    def test_runtime_events_share_turn_id(self):
        from pathlib import Path
        import json
        from runtime.app import IranRuntime
        root_source = Path(__file__).resolve().parents[1] / 'config.json'
        with tempfile.TemporaryDirectory() as directory:
            config = json.loads(root_source.read_text(encoding='utf-8-sig'))
            config['memory']['db']='data/m.db'; config['runtime']['event_log']='data/e.jsonl'; config['runtime']['goals']='data/g.json'
            root=Path(directory); (root/'data').mkdir(); (root/'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            runtime=IranRuntime(root); runtime.handle('پایتخت ایران کجاست؟')
            rows=runtime.events.recent(30); ids={x['turn_id'] for x in rows if x['turn_id'] != 'system'}
            self.assertEqual(len(ids), 1)
            runtime.close()


if __name__ == '__main__':
    unittest.main()
