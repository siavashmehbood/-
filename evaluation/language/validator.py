"""Dataset quality gates for IRAN's 20-language benchmark."""
from __future__ import annotations
from collections import Counter, defaultdict

TIER1 = ("fa","en","ar","tr","fr","de","es","pt","ru","zh","ja","ko","hi","ur","it","id","nl","pl","uk","he")
REQUIRED_CATEGORIES = ("conversation","context","instruction","reasoning")


def validate_suite(cases, require_all_languages=False):
    errors=[]
    counts=Counter(c.language for c in cases)
    ids=Counter(c.case_id for c in cases)
    errors += [f"duplicate_id:{key}" for key,value in ids.items() if value > 1]
    unknown=sorted(set(counts)-set(TIER1))
    if unknown: errors.append("unknown_languages:"+",".join(unknown))
    if require_all_languages:
        missing=[code for code in TIER1 if not counts[code]]
        if missing: errors.append("missing_languages:"+",".join(missing))
    by_language=defaultdict(set)
    for case in cases:
        by_language[case.language].add(case.category)
        if not case.rubric and not case.expected_facts:
            errors.append(f"unscorable:{case.case_id}")
    return {"passed":not errors,"errors":errors,"counts":dict(counts),
            "languages":len(counts),"cases":len(cases)}
