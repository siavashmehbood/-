"""Deterministic offline reasoning + planning bridge for the canonical IRAN pipeline."""
from dataclasses import dataclass, field
from core.reasoning_graph import EvidenceReasoner, Evidence


@dataclass
class ReasoningPlanTrace:
    goal: str
    intent: str
    subgoals: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: float = 1.0
    status: str = "UNRESOLVED"
    replan_required: bool = False


class ReasoningPlanningEngine:
    """Builds explicit, inspectable reasoning traces without pretrained models or APIs."""

    def __init__(self):
        self.evidence = EvidenceReasoner()

    @staticmethod
    def _intent(parsed):
        return str(parsed.get("intent") or "general").lower()

    @staticmethod
    def _goal(text, parsed):
        return str(parsed.get("goal") or text).strip()

    @staticmethod
    def _subgoals(goal, intent, constraints):
        if intent == "debug":
            return ["تعریف دقیق مشکل", "جمع‌آوری شواهد", "جداسازی علت‌های ممکن", "آزمون علت منتخب", "تأیید رفع"]
        if intent in {"build", "planning", "plan"} or any(x in goal for x in ("بساز", "ایجاد", "پیاده", "توسعه")):
            return ["تعریف خروجی", "استخراج محدودیت‌ها", "بررسی وضعیت موجود", "انتخاب تغییر کم‌ریسک", "پیاده‌سازی", "آزمون و ارزیابی"]
        if intent in {"why", "question"}:
            return ["تشخیص سؤال", "جمع‌آوری شواهد", "مقایسه فرضیه‌ها", "بررسی تناقض", "تعیین میزان قطعیت"]
        return ["فهم هدف", "بازیابی زمینه", "جمع‌آوری شواهد", "انتخاب اقدام", "ارزیابی نتیجه"]

    @staticmethod
    def _steps(subgoals):
        steps = []
        for i, title in enumerate(subgoals, 1):
            steps.append({
                "id": i,
                "title": title,
                "depends_on": [i - 1] if i > 1 else [],
                "status": "pending",
                "gate": "observable_result",
            })
        return steps

    def analyze(self, text, parsed, memory=(), knowledge=(), reference="", chain_result=None):
        goal = self._goal(text, parsed)
        intent = self._intent(parsed)
        constraints = list(parsed.get("constraints") or [])
        raw_evidence = []
        for fact in knowledge:
            raw_evidence.append(Evidence(
                text=f"{fact.get('subject', '')}: {fact.get('predicate', '')} = {fact.get('object', '')}",
                weight=float(fact.get("confidence", .7)), reliability=.95, source=str(fact.get("source", "local")),
            ))
        for row in list(memory)[:8]:
            content = row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else str(row)
            if content:
                raw_evidence.append(Evidence(text=str(content), weight=.55, reliability=.75, source="memory"))
        if reference:
            raw_evidence.append(Evidence(text=str(reference), weight=.65, reliability=.8, source="reference"))

        hypotheses = []
        if intent == "debug":
            hypotheses = ["علت منطقی/پیاده‌سازی", "علت پیکربندی یا محیط", "وابستگی یا داده نامناسب"]
        elif intent in {"why", "question"}:
            hypotheses = ["توضیح مستقیم", "توضیح وابسته به زمینه", "شواهد ناکافی"]
        elif intent in {"build", "planning", "plan"}:
            hypotheses = ["تغییر حداقلی", "بازطراحی گسترده", "نیاز به شواهد بیشتر قبل از تغییر"]
        else:
            hypotheses = ["تفسیر اصلی", "تفسیر جایگزین"]

        inference = self.evidence.evaluate(goal, hypotheses, raw_evidence)
        selected = inference.hypotheses[0] if inference.hypotheses else None
        decisions = []
        if selected:
            decisions.append(f"فرضیه منتخب: {selected.name}")
        if reference:
            decisions.append(f"مرجع فعال: {reference}")
        if constraints:
            decisions.append("محدودیت‌ها باید در تمام مراحل حفظ شوند.")
        if inference.uncertainty >= .65:
            decisions.append("قطعیت پایین است؛ قبل از ادعای قطعی شواهد بیشتری لازم است.")

        subgoals = self._subgoals(goal, intent, constraints)
        status = "VERIFIED_CANDIDATE" if inference.confidence >= .65 and raw_evidence else ("PARTIAL" if raw_evidence else "UNKNOWN")
        if chain_result is not None and getattr(chain_result, "status", "") == "VERIFIED_CANDIDATE":
            status = "VERIFIED_CANDIDATE"
            decisions.append("زنجیره استدلال محلی نیز یک نامزد راستی‌آزمایی‌شده ارائه کرده است.")

        # High-confidence verified local facts are stronger than lexical
        # hypothesis matching; do not turn a known fact into artificial doubt.
        if knowledge:
            strongest = max(float(f.get("confidence", 0.0)) for f in knowledge)
            if strongest >= .90:
                inference.confidence = max(inference.confidence, round(strongest, 3))
                inference.uncertainty = round(1.0 - inference.confidence, 3)
                status = "VERIFIED_CANDIDATE"

        trace = ReasoningPlanTrace(
            goal=goal, intent=intent, subgoals=subgoals,
            evidence=[{"text": e.text, "source": e.source, "weight": e.weight, "reliability": e.reliability} for e in raw_evidence[:12]],
            hypotheses=[h.name for h in inference.hypotheses],
            contradictions=list(getattr(selected, "contradictions", []) if selected else []),
            assumptions=list(inference.assumptions) + constraints,
            decisions=decisions,
            steps=self._steps(subgoals),
            confidence=inference.confidence,
            uncertainty=inference.uncertainty,
            status=status,
            replan_required=False,
        )
        return trace

    @staticmethod
    def as_reasoning_dict(trace):
        return {
            "hypotheses": trace.hypotheses,
            "evidence": trace.evidence,
            "uncertainty": trace.uncertainty,
            "conclusion": trace.decisions[0] if trace.decisions else "",
            "subgoals": trace.subgoals,
            "assumptions": trace.assumptions,
            "decisions": trace.decisions,
            "plan_steps": trace.steps,
            "status": trace.status,
            "replan_required": trace.replan_required,
        }

    @staticmethod
    def mark_result(trace, step_id, success, observation=""):
        for step in trace.steps:
            if step["id"] == int(step_id):
                step["status"] = "done" if success else "failed"
                step["observation"] = str(observation)
                if not success:
                    trace.replan_required = True
                    trace.status = "REPLAN_REQUIRED"
                break
        return trace
