"""Run the deterministic Persian conversation benchmark and report the score.

Exit codes:
  0 - score met or exceeded KNOWN_BASELINE
  1 - score regressed below KNOWN_BASELINE
  2 - score did not reach TARGET, but did not regress

KNOWN_BASELINE is the score the canonical runtime actually achieves today; it is
the regression gate. TARGET is the score we want eventually. They are separate
because gating on TARGET would make CI permanently red on a known gap, and
lowering TARGET to whatever the runtime happens to score would turn the check
into a rubber stamp.

The current gap is the `unknown` category: an honest-uncertainty question such as
"آیا فردا ساعت ۸ باران می‌بارد؟" contains the token "ساعت", so ToolRouter diverts
the whole turn to the clock tool before the dialogue layer can return UNKNOWN.
Fixing that requires changing canonical routing behaviour, which is out of scope
for this branch; it is reported rather than hidden.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.persian_conversation_benchmark import PersianConversationBenchmark
from benchmarks.runtime_factory import isolated_runtime_factory

TARGET = 100.0
KNOWN_BASELINE = 90.0
KNOWN_GAP_CATEGORIES = ('unknown',)


def main():
    report = PersianConversationBenchmark().run(isolated_runtime_factory())
    failed = [r['name'] for r in report['results'] if not r['passed']]
    failed_categories = sorted({name.rsplit('_', 1)[0] for name in failed})
    summary = {
        'score': report['score'],
        'passed': report['passed'],
        'total': report['total'],
        'known_baseline': KNOWN_BASELINE,
        'target': TARGET,
        'failed_count': len(failed),
        'failed_categories': failed_categories,
        'known_gap_categories': list(KNOWN_GAP_CATEGORIES),
        'failed_scenarios': failed,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    unexplained = [c for c in failed_categories if c not in KNOWN_GAP_CATEGORIES]
    if unexplained:
        print(f'\nREGRESSION: unexpected failing categories {unexplained}', file=sys.stderr)
        return 1
    if report['score'] < KNOWN_BASELINE:
        print(f'\nREGRESSION: {report["score"]} < known baseline {KNOWN_BASELINE}', file=sys.stderr)
        return 1
    if report['score'] < TARGET:
        print(
            f'\nKnown gap: {report["score"]} < target {TARGET}; '
            f'limited to {failed_categories}. Not a regression.',
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
