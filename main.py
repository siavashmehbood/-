import json, sys
from pathlib import Path
from core.health import check_system
from core.reasoning import Reasoner
from runtime.app import IranRuntime
from self.evaluator import Evaluator
from self.improvement import ImprovementManager
from self.model import SelfModel
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')

def run_cli():
    runtime=IranRuntime(ROOT); identity=SelfModel(CONFIG['name'],CONFIG['version']); evaluator=Evaluator(ROOT); improver=ImprovementManager(ROOT,CONFIG['self_improvement']['sandbox']); reasoner=Reasoner()
    print(f"ایران {CONFIG['version']} | provider={runtime.provider.name}")
    try:
        while True:
            try: text=input('You > ').strip()
            except (EOFError,KeyboardInterrupt): break
            cmd=text.lower()
            if cmd in {'/exit','/quit'}: break
            if cmd=='/status': print({'health':check_system(ROOT,runtime.brain),'metrics':runtime.metrics(),'goals':runtime.goals.list(status='active')}); continue
            if cmd=='/health': print(check_system(ROOT,runtime.brain)); continue
            if cmd=='/metrics': print(runtime.metrics()); continue
            if cmd=='/memory': print(runtime.memory.recent(CONFIG['memory']['max_history'])); continue
            if cmd=='/events': print(runtime.events.recent()); continue
            if cmd=='/trace':
                for event in runtime.events.recent(20):
                    print(f"{event['time']} | {event['event']} | {event.get('data', {})}")
                continue
            if cmd=='/quality':
                rows=[e for e in runtime.events.recent(100) if e['event']=='evaluation_completed']
                print(rows[-1] if rows else 'هنوز ارزیابی پاسخ ثبت نشده است.')
                continue
            if cmd=='/benchmark':
                result=runtime.roadmap_benchmark()
                print({'score': result.score, 'passed': result.passed, 'cases': [item.__dict__ for item in result.cases]})
                continue
            if cmd=='/benchmark100':
                from self.scenario_benchmark import PersianScenarioBenchmark
                result=PersianScenarioBenchmark().run(runtime)
                print({'score': result.score, 'metrics': result.metrics, 'total': len(result.results)})
                continue
            if cmd.startswith('/knowledge '):
                print(runtime.knowledge.query(text[11:].strip(), limit=20))
                continue
            if cmd=='/tools': print(runtime.registry.list()); continue
            if cmd=='/evaluate': print(evaluator.smoke_test()); continue
            if cmd=='/sandbox': snap=improver.create_snapshot(); print(snap); print(evaluator.evaluate_candidate(snap['snapshot'])); continue
            if cmd=='/reason': print(reasoner.analyze(input('Goal > ').strip())); continue
            if cmd=='/help': print('/status /health /metrics /memory /events /trace /quality /benchmark /knowledge QUERY /tools /evaluate /sandbox /reason /goal TITLE /complete ID /tool NAME /run TEXT /exit'); continue
            if text: print('ایران > '+runtime.handle(text))
    finally: runtime.close()
if __name__=='__main__': run_cli()
