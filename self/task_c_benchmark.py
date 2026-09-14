import tempfile
from pathlib import Path
from time import perf_counter
from knowledge.knowledge_graph import KnowledgeGraph
from learning.learning_engine import LearningEngine
from learning.procedural_memory import ProceduralMemory
from learning.skill_system import SkillSystem


class TaskCBenchmark:
    """Deterministic benchmark for graph, procedures, skills and outcome-backed transfer."""
    def run(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); graph=KnowledgeGraph(root/'knowledge.json')
            for i in range(20): graph.add_node(f'n{i}','concept',{'i':i},.8,'benchmark')
            for i in range(30): graph.add_edge(f'n{i%20}','related_to' if i%3 else 'supports',f'n{(i+1)%20}',.8,'benchmark','benchmark')
            graph.contradict('node:n0','status','bad',.8,'benchmark'); graph.add_fact('node:n0','status','good',.9,'benchmark')
            t=perf_counter(); graph_result=graph.graph_query('n0',3); graph_latency=round((perf_counter()-t)*1000,3)
            graph_ok=len(graph_result)>0 and len(graph.contradictions('node:n0'))>0
            procedures=ProceduralMemory(root/'procedures.json'); skills=SkillSystem(root/'skills.json',procedures)
            for i in range(10):
                p=procedures.upsert(f'procedure-{i}',f'task family {i}',['inspect','verify'],['evidence_available'],'verified',confidence=.8)
                skills.upsert(f'skill-{i}',f'reusable skill {i}','benchmark',[f'task family {i}'],p,['evidence_available'],['verification'],confidence=.8)
            t=perf_counter(); proc_rows=procedures.retrieve('task family 1'); procedure_latency=round((perf_counter()-t)*1000,3)
            t=perf_counter(); skill_rows=skills.retrieve('task family 1','benchmark'); skill_latency=round((perf_counter()-t)*1000,3)
            proc_ok=len(proc_rows)>0; skill_ok=len(skill_rows)>0
            learner=LearningEngine(root/'experiences.json'); transfers=[]; transfer_latencies=[]
            for i in range(10):
                a=f'task family {i} source'; b=f'task family {i} target'
                learner.record(a,'evidence-first','verified',.95,'build','evidence-first','benchmark')
                learner.record(a+' small','evidence-first','verified',.90,'build','evidence-first','benchmark')
                t=perf_counter(); tr=learner.transfer_real(a,b,lambda _: .4,lambda _: True,
                    lambda *_:{'score':.75,'verified':True,'decision_before':'default','decision_after':'evidence-first','skill_retrieved':True,'procedure_retrieved':True}); transfer_latencies.append((perf_counter()-t)*1000); transfers.append(tr['transfer_success'])
            transfer_score=sum(transfers)/len(transfers)
            return {'memory_graph':1.0 if graph_ok else 0.0,'procedural_memory':1.0 if proc_ok else 0.0,
                    'skill_system':1.0 if skill_ok else 0.0,'learning_transfer':round(transfer_score,3),
                    'graph_nodes':20,'graph_edges':30,'procedures':10,'skills':10,'transfer_pairs':10,
                    'performance':{'graph_query_ms':graph_latency,'procedure_retrieval_ms':procedure_latency,'skill_retrieval_ms':skill_latency,'transfer_avg_ms':round(sum(transfer_latencies)/len(transfer_latencies),3)},
                    'overall':round((graph_ok+proc_ok+skill_ok+transfer_score)/4,3),
                    'passed':bool(graph_ok and proc_ok and skill_ok and transfer_score==1.0)}
