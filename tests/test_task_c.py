import tempfile
import unittest
from pathlib import Path
from knowledge.knowledge_graph import KnowledgeGraph
from learning.procedural_memory import ProceduralMemory
from learning.skill_system import SkillSystem
from learning.learning_engine import LearningEngine


class TaskCTests(unittest.TestCase):
    def test_memory_graph_typed_edges_multihop_and_contradiction(self):
        with tempfile.TemporaryDirectory() as d:
            graph=KnowledgeGraph(Path(d)/'knowledge.json')
            for i in range(20): graph.add_node(f'n{i}','concept',{'i':i},.8,'test')
            for i in range(30): graph.add_edge(f'n{i%20}', 'related_to' if i%2 else 'supports', f'n{(i+1)%20}', .8, 'test','test')
            graph.contradict('node:n0','status','bad',.8,'test'); graph.add_fact('node:n0','status','good',.9,'test')
            self.assertGreaterEqual(graph.stats()['facts'],20)
            self.assertGreaterEqual(len(graph.graph_query('n0',3)),1)
            self.assertGreaterEqual(len(graph.contradictions('node:n0')),1)

    def test_procedure_skill_lifecycle_persists(self):
        with tempfile.TemporaryDirectory() as d:
            p=ProceduralMemory(Path(d)/'procedures.json')
            proc=p.upsert('repair','repair task',['inspect','verify'],['evidence_available'],'fixed',['outcome_verified'],['verification_failed'],['exp1'],.8)
            self.assertTrue(p.retrieve('repair task'))
            self.assertFalse(p.check_preconditions(proc,{} )['applicable'])
            self.assertTrue(p.check_preconditions(proc,{'evidence':True})['applicable'])
            skills=SkillSystem(Path(d)/'skills.json',p)
            skill=skills.upsert('repair','repair safely','debug',['repair'],proc,['evidence_available'],['verification'],'low',.8)
            self.assertTrue(skills.retrieve('repair','debug'))
            self.assertTrue(skills.apply(skill['skill_id'],{'evidence':True})['applied'])
            skills.update_outcome(skill['skill_id'],False); skills.disable(skill['skill_id'])
            self.assertFalse(skills.retrieve('repair','debug'))
            p2=ProceduralMemory(Path(d)/'procedures.json'); s2=SkillSystem(Path(d)/'skills.json',p2)
            self.assertTrue(p2.retrieve('repair task'))
            self.assertEqual(len(s2.skills),1)

    def test_real_transfer_requires_verified_improvement(self):
        with tempfile.TemporaryDirectory() as d:
            learner=LearningEngine(Path(d)/'experiences.json')
            learner.record('ساخت ابزار امن محلی','evidence-first','ok',.95,'build','evidence-first','tools')
            learner.record('ساخت ابزار امن کوچک','evidence-first','ok',.90,'build','evidence-first','tools')
            calls=[]
            def baseline(task): return .40
            def apply(payload): calls.append(payload); return True
            def verify(task,applied): return {'score':.75,'verified':True,'decision_before':'default','decision_after':'evidence-first','skill_retrieved':True,'procedure_retrieved':True}
            result=learner.transfer_real('ساخت ابزار امن محلی','ساخت ابزار امن جدید',baseline,apply,verify)
            self.assertTrue(result['transfer_success']); self.assertGreater(result['improvement'],0); self.assertTrue(calls)

    def test_real_transfer_rejects_unverified_or_worse_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            learner=LearningEngine(Path(d)/'experiences.json')
            learner.record('task A secure','a','ok',.95,'build','a','tools')
            learner.record('task A secure small','a','ok',.9,'build','a','tools')
            bad=learner.transfer_real('task A secure','task B secure',lambda _: .8,lambda _: True,lambda *_:{'score':.7,'verified':True})
            self.assertFalse(bad['transfer_success'])
            unverified=learner.transfer_real('task A secure','task B secure',lambda _: .4,lambda _: True,lambda *_:{'score':.9,'verified':False})
            self.assertFalse(unverified['transfer_success'])


if __name__ == '__main__': unittest.main()
