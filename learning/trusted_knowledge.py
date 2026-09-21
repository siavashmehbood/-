"""Deterministic trusted-knowledge bootstrap for local IRAN.

No web access, model, embeddings, or external service is used here. The caller
provides source text; this module only evaluates relevance, source independence,
claim overlap and extraction quality before creating a human-review proposal.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import json
import re
from urllib.parse import urlparse

_STOP = {
    "the", "and", "or", "of", "to", "in", "on", "for", "a", "an", "is", "are", "was", "were",
    "this", "that", "with", "from", "by", "as", "at", "it", "its", "be", "has", "have", "had",
    "history", "edit", "jump", "content", "main", "menu", "section", "toggle", "subsection",
    "و", "در", "از", "به", "که", "این", "آن", "با", "برای", "است", "هست", "شد", "های", "را",
}
_BAD_MARKERS = {"�", "\ufffd"}

@dataclass
class SourceEvidence:
    source_id: str
    url: str
    title: str
    text: str
    source_confidence: float = 0.5
    relevance: float = 0.0
    domain: str = ""
    claims: list[str] | None = None
    extraction_complete: bool = True
    retrieved_at: str = ""
    source_type: str = "reference"


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[\w\u0600-\u06ff]+", str(text).lower())
    return {x for x in raw if len(x) > 1 and x not in _STOP}


def _domain(url: str) -> str:
    try:
        host = urlparse(str(url)).netloc.lower().split(":")[0]
        return ".".join(host.removeprefix("www.").split(".")[-2:])
    except Exception:
        return ""


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return []
    # Keep sentence boundaries but reject navigation-only fragments.
    rows = re.split(r"(?<=[.!?؟؛])\s+|\n+", text)
    return [x.strip(" -–—|•") for x in rows if len(x.strip()) >= 25]


def _claim_key(text: str) -> str:
    return " ".join(sorted(_tokens(text)))


def _similar(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    return len(x & y) / max(1, len(x | y))


def _looks_broken(text: str) -> bool:
    t = str(text).strip()
    if not t or any(m in t for m in _BAD_MARKERS):
        return True
    # A navigation tail such as "history, edit, and" is not a claim.
    words = re.findall(r"[\w\u0600-\u06ff]+", t)
    if len(words) < 5:
        return True
    if t.lower().rstrip(".,;:،") in {"history edit and", "history edit"}:
        return True
    if re.search(r"(?:^|\s)(and|or|و|یا|و همچنین)\s*[.,;،]?$", t, re.I):
        return True
    return False


def extract_claims(text: str, topic: str = "") -> tuple[list[str], bool]:
    # Web pages may contain a single Unicode replacement glyph from an HTML entity.
    # Repair that harmless encoding artifact instead of discarding the whole source.
    text = str(text).replace("\ufffd", " ")
    rows = _sentences(text)
    topic_tokens = _tokens(topic)
    claims = []
    # Keep the safety gate for obvious truncated navigation fragments.
    broken_fragment = bool(re.search(r"\bhistory\s*[,?]?\s*edit\s*[,?]?\s*and\b", str(text), re.I)) or any(m in str(text) for m in _BAD_MARKERS)
    for row in rows:
        # Ignore obvious Wikipedia/navigation chrome and unrelated tiny fragments.
        low = row.lower()
        if any(x in low for x in ("jump to content", "main menu", "toggle history subsection", "contents move to sidebar")):
            continue
        if _looks_broken(row):
            broken_fragment = True
            continue
        overlap = len(_tokens(row) & topic_tokens) / max(1, len(topic_tokens)) if topic_tokens else 1.0
        if topic_tokens and overlap < 0.08:
            continue
        claims.append(row)
    # A few malformed/navigation fragments do not invalidate an otherwise rich page,
    # but a page consisting of one claim plus navigation corruption is not evidence.
    complete = bool(claims) and not (broken_fragment and len(claims) <= 1)
    return claims[:40], complete


def evaluate_source(source: dict, topic: str) -> SourceEvidence:
    text = str(source.get("text", ""))
    title = str(source.get("title", ""))
    combined = f"{title} {topic}"
    relevance = _similar(combined, f"{title} {text[:3000]}")
    if _tokens(topic):
        relevance = max(relevance, len(_tokens(topic) & _tokens(title)) / max(1, len(_tokens(topic))))
    claims, complete = extract_claims(text, topic)
    if not claims:
        complete = False
    return SourceEvidence(
        source_id=str(source.get("source_id") or source.get("id") or _domain(source.get("url", "")) or "source"),
        url=str(source.get("url", "")), title=title, text=text,
        source_confidence=max(0.0, min(1.0, float(source.get("confidence", source.get("source_confidence", .5))))),
        relevance=round(max(0.0, min(1.0, relevance)), 3), domain=_domain(source.get("url", "")),
        claims=claims, extraction_complete=complete,
        retrieved_at=str(source.get("retrieved_at", "")), source_type=str(source.get("source_type", "reference")),
    )


class TrustedKnowledgeBootstrap:
    """Build reviewable trusted-knowledge proposals; never writes durable memory itself."""
    VERSION = "1.0"

    def build(self, topic: str, sources: list[dict]) -> dict:
        evidence = [evaluate_source(s, topic) for s in sources]
        usable = [e for e in evidence if e.relevance >= .25 and e.extraction_complete]
        domains = {e.domain or e.source_id for e in usable}
        independent = len(domains)

        conflicts = []
        for i, left in enumerate(usable):
            for right in usable[i+1:]:
                if left.domain == right.domain: continue
                for a in left.claims or []:
                    for b in right.claims or []:
                        if _similar(a, b) < .45: continue
                        neg = lambda t: bool(re.search(r"\b(not|never|false)\b|نیست|نمی", t.lower()))
                        numbers = lambda t: set(re.findall(r"\d+(?:[.,]\d+)?", t))
                        if neg(a) != neg(b) or (numbers(a) and numbers(b) and numbers(a) != numbers(b)):
                            conflicts.append({"left": a, "right": b, "sources": [left.source_id,right.source_id], "reason": "potential_numeric_or_negation_conflict"})
        clusters: list[dict] = []
        for e in usable:
            for claim in e.claims or []:
                # Web sources often paraphrase the same fact. Use a conservative token-overlap threshold.
                match = next((c for c in clusters if _similar(claim, c["representative"]) >= .35), None)
                if match is None:
                    clusters.append({"representative": claim, "claims": [], "sources": set()})
                    match = clusters[-1]
                match["claims"].append({"source_id": e.source_id, "text": claim, "domain": e.domain})
                match["sources"].add(e.domain or e.source_id)

        agreements = []
        for c in clusters:
            independent_sources = sorted(x for x in c["sources"] if x)
            if len(independent_sources) >= 2:
                agreements.append({
                    "claim": c["representative"],
                    "independent_sources": independent_sources,
                    "support": len(c["claims"]),
                })

        # If two reputable pages paraphrase the same topic but token clustering misses
        # the wording, retain the strongest cross-source pair as corroboration evidence.
        if not agreements and len(usable) >= 2 and _tokens(topic):
            best = None
            for i, left in enumerate(usable):
                for right in usable[i + 1:]:
                    if left.domain == right.domain: continue
                    for lc in left.claims or []:
                        for rc in right.claims or []:
                            overlap = len((_tokens(lc) & _tokens(rc) & _tokens(topic)))
                            sim = _similar(lc, rc)
                            if overlap >= 1 and sim >= .10 and (best is None or sim > best[0]):
                                best = (sim, lc, rc, left, right)
            if best:
                _, lc, rc, left, right = best
                agreements.append({
                    "claim": lc,
                    "corroborating_claim": rc,
                    "independent_sources": sorted({left.domain or left.source_id, right.domain or right.source_id}),
                    "support": 2,
                    "corroboration": "cross_source_paraphrase",
                })

        if conflicts:
            agreements = []

        avg_conf = sum(e.source_confidence * e.relevance for e in usable) / max(1, len(usable))
        agreement_factor = min(1.0, len(agreements) / max(1, len(usable)))
        independence_factor = min(1.0, independent / 2)
        confidence = round(.45 * avg_conf + .30 * agreement_factor + .25 * independence_factor, 3)
        issues = ["source_conflict"] if conflicts else []
        if len(usable) < 2: issues.append("evidence_insufficient")
        if independent < 2: issues.append("sources_not_independent")
        if not agreements: issues.append("no_cross_source_agreement")
        if any(not e.extraction_complete for e in evidence): issues.append("incomplete_extraction")
        if any(e.relevance < .25 for e in evidence): issues.append("weak_source_relevance")

        status = "ready_for_review" if not issues else "needs_review"
        proposal_id = "tk_" + __import__("hashlib").sha256(
            json.dumps({"topic": topic, "sources": [{"url":e.url,"text":e.text} for e in evidence]}, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:20]
        return {
            "version": self.VERSION, "proposal_id": proposal_id, "kind": "trusted_knowledge.bootstrap",
            "topic": str(topic), "status": status, "confidence": confidence,
            "agreements": agreements, "issues": issues, "conflicts": conflicts,
            "independent_source_count": independent,
            "sources": [asdict(e) for e in evidence],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
