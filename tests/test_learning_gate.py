import json
import tempfile
import unittest
from pathlib import Path

from knowledge.knowledge_graph import KnowledgeGraph
from learning.learning_engine import LearningEngine
from memory.store import Memory
from security.learning_gate import LearningGate


class LearningGateTests(unittest.TestCase):
    def make(self):
        root=Path(tempfile.mkdtemp(prefix='iran_gate_'))
        gate=LearningGate(root/'proposals.json')
        memory=Memory(root/'memory.db',gate=gate)
        knowledge=KnowledgeGraph(root/'knowledge.json',gate=gate)
        learning=LearningEngine(root/'experiences.json',gate=gate)
        return root,gate,memory,knowledge,learning

    def test_durable_learning_never_persists_before_approval(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            k=knowledge.add_fact('s','p','o',.9,'test')
            m=memory.add_semantic_fact('s','p','o',.9,'test')
            l=learning.record('g','a','r',.9,intent='test',strategy='test',domain='test')
            self.assertEqual({k['kind'],m['kind'],l['kind']},{'knowledge.add_fact','memory.add_semantic_fact','learning.record_experience'})
            self.assertEqual(len(knowledge.facts),0)
            self.assertEqual(memory.semantic_stats()['facts'],0)
            self.assertEqual(learning.stats()['experiences'],0)
            self.assertEqual(len(gate.pending()),3)
        finally:
            memory.close()

    def test_request_count_and_xp_are_locked_to_one_million_per_request(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            for i in range(3):
                learning.record(f'goal-{i}','respond',f'result-{i}',1.0)
            stats=gate.stats()
            self.assertEqual(stats['requests'],3)
            self.assertEqual(stats['xp_units'],stats['requests'])
            self.assertEqual(stats['xp'],stats['requests'] * 1_000_000)
        finally:
            memory.close()
    def test_approval_is_the_only_commit_path(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            proposal=knowledge.add_fact('s','p','o',.9,'test')
            self.assertEqual(knowledge.query('s'),[])
            with gate.bypass():
                knowledge.add_fact(proposal['payload']['subject'],proposal['payload']['predicate'],proposal['payload']['object'],proposal['payload']['confidence'],proposal['payload']['source'])
            gate.decide(proposal['proposal_id'],'approved')
            self.assertEqual(len(knowledge.query('s')),1)
            self.assertEqual(gate.stats()['approved'],1)
        finally:
            memory.close()

    def test_distinct_learning_creates_new_proposal(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            first=learning.record('آب چه دمایcc میجوشد؟','respond','۱۰۰ درجه سانتی‌گراد',1.0,intent='general',strategy='conversation',domain='dialogue')
            self.assertEqual(first['status'],'pending')
            gate.decide(first['proposal_id'],'approved')
            second=learning.record('پایتخت فرانسه چیست؟','respond','پاریس',1.0,intent='general',strategy='conversation',domain='dialogue')
            self.assertIsNotNone(second)
            self.assertEqual(second['status'],'pending')
            self.assertNotEqual(first['proposal_id'],second['proposal_id'])
        finally:
            memory.close()

    def test_approved_learning_is_not_proposed_again(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            first=learning.record('آب چه دمایی میجوشد؟','respond','۱۰۰ درجه سانتی‌گراد',1.0,intent='general',strategy='conversation',domain='dialogue')
            self.assertEqual(first['status'],'pending')
            gate.decide(first['proposal_id'],'approved')
            with gate.bypass():
                learning.record('آب چه دمایی میجوشد؟','respond','۱۰۰ درجه سانتی‌گراد',1.0,intent='general',strategy='conversation',domain='dialogue')
            second=learning.record('آب چه دمایی میجوشد؟','respond','۱۰۰ درجه سانتی‌گراد',1.0,intent='general',strategy='conversation',domain='dialogue')
            self.assertIsNone(second)
            self.assertEqual(len(gate.pending()),0)
        finally:
            memory.close()


if __name__=='__main__':
    unittest.main()
