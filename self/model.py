from dataclasses import dataclass,field
from datetime import datetime

@dataclass
class SelfModel:
    name:str='ایران'
    version:str='1.0.0'
    capabilities:list[str]=field(default_factory=lambda:[
        'conversation','persian-language-understanding','context-resolution','memory','episodic-learning',
        'world-model','knowledge-graph','reasoning','hypothesis-testing','prediction','goal-management',
        'planning','decision-making','tool-routing','observation','anomaly-detection','evaluation',
        'reflection','sandboxed-self-improvement','rollback','event-log','security-policy',
        'multi-intent-parsing','constraint-extraction','causal-tracing','counterfactual-ranking',
        'persistent-prediction-calibration','strategy-derivation','temporal-world-state','typed-memory-graph',
        'procedural-memory','persistent-skills','outcome-backed-learning-transfer'])
    limitations:list[str]=field(default_factory=lambda:[
        'local-language-engine-is-symbolic','no-large-neural-language-model','no-vision','no-voice',
        'no-autonomous-deployment','predictions-are-estimates','knowledge-is-not-automatically-universal'])
    last_check:str=''
    def snapshot(self):
        self.last_check=datetime.now().isoformat(timespec='seconds')
        return {'name':self.name,'version':self.version,'capabilities':self.capabilities,'limitations':self.limitations,'last_check':self.last_check}
