"""Evidence-driven capability transfer policy; forbids blind cross-family merging."""
from __future__ import annotations


def choose_transfer(gap, same_architecture=False, forgetting_risk=False):
    """Return the least invasive justified intervention for a measured gap."""
    if float(gap.get("delta_to_best",0)) <= float(gap.get("tolerance",3)):
        return "none"
    owner=gap.get("owner","foundation")
    if owner in {"memory","reasoning_orchestration","tool_policy","verification"}:
        return "fix_iran"
    kind=gap.get("kind","language")
    if kind in {"style","normalization","format"}:
        return "sft_or_lora"
    if gap.get("teacher_advantage_repeated") and gap.get("teacher_license_allows_transfer"):
        return "adapter_with_replay" if forgetting_risk else "distillation"
    if same_architecture and gap.get("merge_evidence"):
        return "research_weight_merge"
    return "collect_evidence"
