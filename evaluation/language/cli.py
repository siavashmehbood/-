"""Run a tracked benchmark against an already-running loopback model server."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from language_engine import IranLanguageEngine
from language_engine.backends.local_http import LocalHTTPBackend
from .dataset_loader import load_dataset
from .runner import BenchmarkRunner
from .reports import summarize
from .validator import validate_suite


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--dataset",required=True)
    parser.add_argument("--endpoint",default="http://127.0.0.1:8000/v1/chat/completions")
    parser.add_argument("--output")
    args=parser.parse_args(argv)
    cases=load_dataset(args.dataset)
    validation=validate_suite(cases)
    if not validation["passed"]: raise SystemExit("invalid dataset: "+",".join(validation["errors"]))
    engine=IranLanguageEngine(LocalHTTPBackend(args.model,args.endpoint))
    rows=BenchmarkRunner(engine).run(cases)
    report={"model":args.model,"dataset":str(args.dataset),"validation":validation,
            "summary":summarize(rows),"rows":rows}
    payload=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output: Path(args.output).write_text(payload,encoding="utf-8")
    else: print(payload)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
