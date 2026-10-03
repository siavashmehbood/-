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


    def test_payload_and_returned_rows_are_independent_snapshots(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            payload={'subject':'snapshot','metadata':{'items':['original']}}
            proposal=gate.request('knowledge.add_fact',payload,'snapshot fixture')
            payload['metadata']['items'].append('caller mutation')
            proposal['payload']['metadata']['items'].append('return mutation')

            stored=gate.get(proposal['proposal_id'])
            self.assertEqual(stored['payload']['metadata']['items'],['original'])

            pending=gate.pending(10)
            pending[0]['payload']['metadata']['items'].append('pending mutation')
            stored_again=gate.get(proposal['proposal_id'])
            self.assertEqual(stored_again['payload']['metadata']['items'],['original'])
        finally:
            memory.close()

    def test_invalid_request_shapes_fail_without_poisoning_durable_queue(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            with self.assertRaises(ValueError):
                gate.request('   ',{})
            with self.assertRaises(TypeError):
                gate.request('memory.add_lesson',[])
            with self.assertRaises(TypeError):
                gate.request('memory.add_lesson',None)
            self.assertEqual(gate.history(),[])
            reloaded=LearningGate(root/'proposals.json')
            self.assertEqual(reloaded.history(),[])
        finally:
            memory.close()

    def test_pending_cursor_is_stable_when_new_rows_arrive_and_cursor_becomes_terminal(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            proposals=[
                gate.request('memory.add_lesson',{'goal':f'page-{index}','lesson':'safe'})
                for index in range(5)
            ]
            first=gate.pending_page(2)
            self.assertEqual(
                [row['proposal_id'] for row in first['items']],
                [proposals[4]['proposal_id'],proposals[3]['proposal_id']],
            )
            self.assertTrue(first['has_more'])
            cursor=first['next_cursor']

            newest=gate.request(
                'memory.add_lesson',{'goal':'newest-after-page','lesson':'safe'}
            )
            gate.decide(cursor,'rejected')
            second=gate.pending_page(2,cursor)
            self.assertEqual(
                [row['proposal_id'] for row in second['items']],
                [proposals[2]['proposal_id'],proposals[1]['proposal_id']],
            )
            seen={row['proposal_id'] for row in first['items']+second['items']}
            self.assertNotIn(newest['proposal_id'],seen)
            self.assertEqual(len(seen),4)

            third=gate.pending_page(2,second['next_cursor'])
            self.assertEqual(
                [row['proposal_id'] for row in third['items']],
                [proposals[0]['proposal_id']],
            )
            self.assertFalse(third['has_more'])
            self.assertIsNone(third['next_cursor'])
        finally:
            memory.close()

    def test_page_limits_filters_and_unknown_cursors_fail_safely(self):
        root,gate,memory,knowledge,learning=self.make()
        try:
            proposals=[
                gate.request('memory.add_lesson',{'goal':f'filter-{index}','lesson':'safe'})
                for index in range(4)
            ]
            self.assertEqual(gate.pending(0),[])
            self.assertEqual(gate.pending(-5),[])
            self.assertEqual(gate.history(0),[])
            self.assertEqual(
                gate.pending_page(0),
                {'items':[],'next_cursor':None,'has_more':False},
            )
            filtered=gate.pending_page(
                10,proposal_ids=[proposals[0]['proposal_id'],proposals[2]['proposal_id']]
            )
            self.assertEqual(
                [row['proposal_id'] for row in filtered['items']],
                [proposals[2]['proposal_id'],proposals[0]['proposal_id']],
            )
            with self.assertRaises(ValueError):
                gate.pending_page(2,'missing-proposal-id')
            with self.assertRaises(ValueError):
                gate.pending_page('not-an-integer')
        finally:
            memory.close()


if __name__=='__main__':
    unittest.main()
