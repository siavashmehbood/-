from pathlib import Path
from runtime.app import IranRuntime
from learning.autonomous_improvement import AutonomousImprovementEngine

ROOT = Path(__file__).resolve().parent
runtime = IranRuntime(ROOT)
engine = AutonomousImprovementEngine(ROOT)
try:
    result = engine.run(runtime, 200)
    print("AUTONOMOUS_200_RESULT")
    print(result)
finally:
    runtime.close()
