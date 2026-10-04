"""Offline command that verifies the repository is ready for real local model runs."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from .readiness import audit
from .candidate_registry import eligible_foundations


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=str(Path(__file__).resolve().parents[2]))
    args=p.parse_args(argv)
    result=audit(args.root)
    payload={"ready":result.ready,"reasons":list(result.reasons),
             "candidates":list(result.candidates),
             "eligible":[{"candidate_id":x.candidate_id,"model_id":x.model_id,
                          "revision":x.revision,"license":x.license_id}
                         for x in eligible_foundations(__import__("json").loads((Path(args.root)/"evaluation/language/candidates.json").read_text(encoding="utf-8")))]}
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return 0 if result.ready else 2


if __name__=="__main__": raise SystemExit(main())
