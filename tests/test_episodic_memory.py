import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from memory.store import Memory
from memory.episodic import EpisodicMemory

class EpisodicMemoryTests(unittest.TestCase):
    def test_yesterday_retrieval_is_time_scoped(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory(Path(d)/'m.db')
            yesterday=(datetime.now()-timedelta(days=1)).replace(microsecond=0).isoformat()
            today=datetime.now().replace(microsecond=0).isoformat()
            m.conn.execute('INSERT INTO memories(kind,content,importance,created_at,confidence,source) VALUES(?,?,?,?,?,?)',('user','بحث معماری هسته ایران',.9,yesterday,.9,'test'))
            m.conn.execute('INSERT INTO memories(kind,content,importance,created_at,confidence,source) VALUES(?,?,?,?,?,?)',('user','موضوع امروز فروشگاه کتاب',.9,today,.9,'test'))
            m.conn.commit()
            out=EpisodicMemory(m).retrieve('دیروز درباره هسته ایران چی گفتیم',8)
            self.assertTrue(out)
            self.assertEqual(out[0]['content'],'بحث معماری هسته ایران')
            self.assertEqual(EpisodicMemory(m).summarize('دیروز درباره هسته ایران چی گفتیم')['temporal'],'دیروز')
            m.close()

    def test_topic_retrieval_uses_relevant_episode(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory(Path(d)/'m.db')
            m.add('user','بحث درباره معماری حافظه و بازیابی تجربه',.9,.9,'test')
            result=EpisodicMemory(m).summarize('درباره حافظه چی گفتیم',4)
            self.assertEqual(result['count'],1)
            self.assertIn('معماری حافظه',result['episodes'][0]['content'])
            m.close()

if __name__=='__main__': unittest.main()
