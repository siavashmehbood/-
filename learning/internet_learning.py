"""Controlled internet learning pipeline for IRAN.

Internet is evidence acquisition only. Web content can update durable knowledge
when independently corroborated and low-risk; it can never modify source code,
permissions, security policy, or executable configuration.
"""
from __future__ import annotations

from datetime import datetime
from html import unescape
from pathlib import Path
import hashlib
import json
import re
import urllib.parse
import urllib.request

from learning.trusted_knowledge import TrustedKnowledgeBootstrap


class InternetLearningEngine:
    VERSION = "1.0"

    def __init__(self, runtime):
        self.runtime = runtime
        self.root = Path(runtime.root)
        self.state_path = self.root / "data" / "internet_learning.json"
        self.state = {"cycles": 0, "learned": 0, "rejected": 0, "last": None}
        self._load()
        self.trusted = TrustedKnowledgeBootstrap()

    def _load(self):
        try:
            self.state.update(json.loads(self.state_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    @staticmethod
    def _strip_html(raw: str) -> str:
        raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", raw)
        raw = re.sub(r"(?is)<!--.*?-->", " ", raw)
        raw = re.sub(r"(?is)<[^>]+>", " ", raw)
        return re.sub(r"\\s+", " ", unescape(raw)).strip()

    def fetch(self, url: str, max_chars: int = 30000) -> dict:
        self.runtime.internet_access.require()
        if not str(url).lower().startswith(("http://", "https://")):
            raise ValueError("only http/https URLs are allowed")
        req = urllib.request.Request(str(url), headers={"User-Agent": "IRAN-Cognitive/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(max_chars * 4).decode("utf-8", errors="replace")
        text = self._strip_html(raw)[:max_chars]
        return {"url": str(url), "title": self._title(raw) or str(url), "text": text}

    @staticmethod
    def _title(raw: str) -> str:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        return re.sub(r"\\s+", " ", unescape(m.group(1))).strip() if m else ""

    def search(self, topic: str, limit: int = 5) -> list[str]:
        self.runtime.internet_access.require()
        q = urllib.parse.quote_plus(str(topic).strip())
        url = "https://html.duckduckgo.com/html/?q=" + q
        req = urllib.request.Request(url, headers={"User-Agent": "IRAN-Cognitive/1.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            html = response.read(120000).decode("utf-8", errors="replace")
        found = []
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"', html):
            href = unescape(m.group(1))
            if href.startswith("//"): href = "https:" + href
            if href.startswith("http") and href not in found:
                found.append(href)
            if len(found) >= int(limit):
                break
        return found

    def _trusted_fallback_urls(self, topic: str) -> list[str]:
        """Fallback to maintained primary/reference sources when search engines return no links."""
        t = str(topic).lower()
        if "python" in t or "program" in t:
            return [
                "https://docs.python.org/3/tutorial/",
                "https://docs.python.org/3/library/unittest.html",
                "https://realpython.com/python-testing/",
            ]
        if "test" in t or "debug" in t or "software" in t:
            return [
                "https://docs.python.org/3/library/unittest.html",
                "https://docs.pytest.org/en/stable/getting-started.html",
                "https://realpython.com/python-testing/",
            ]
        if "algorithm" in t or "data structure" in t:
            return [
                "https://cp-algorithms.com/",
                "https://en.wikipedia.org/wiki/Algorithm",
                "https://docs.python.org/3/howto/sorting.html",
            ]
        if "information retrieval" in t or "retrieval" in t:
            return [
                "https://nlp.stanford.edu/IR-book/",
                "https://en.wikipedia.org/wiki/Information_retrieval",
            ]
        if "knowledge representation" in t or "reasoning" in t:
            return [
                "https://plato.stanford.edu/entries/logic-classical/",
                "https://en.wikipedia.org/wiki/Knowledge_representation_and_reasoning",
            ]
        if "planning" in t:
            return [
                "https://en.wikipedia.org/wiki/Automated_planning_and_scheduling",
                "https://www.cs.cmu.edu/~epxing/Class/10708-19/notes/lecture-1.pdf",
            ]
        return [
            "https://en.wikipedia.org/wiki/" + urllib.parse.quote(str(topic).replace(" ", "_")),
        ]

    def learn(self, topic: str, urls: list[str] | None = None, auto: bool = True) -> dict:
        self.runtime.internet_access.require()
        topic = str(topic).strip()
        if not topic:
            return {"ok": False, "reason": "empty_topic"}

        urls = [u for u in (urls or []) if str(u).startswith(("http://", "https://"))]
        if not urls:
            urls = self.search(topic, 5)
        if not urls:
            urls = self._trusted_fallback_urls(topic)

        sources = []
        errors = []
        for url in urls[:8]:
            try:
                item = self.fetch(url)
                item["source_id"] = hashlib.sha256(url.encode()).hexdigest()[:12]
                item["confidence"] = .72
                sources.append(item)
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)[:300]})

        if not sources:
            self.state["rejected"] += 1
            self.state["last"] = {"topic": topic, "status": "no_sources", "errors": errors}
            self._save()
            return {"ok": False, "reason": "no_sources", "errors": errors}

        proposal = self.trusted.build(topic, sources)
        result = {
            "ok": True, "topic": topic, "sources_fetched": len(sources),
            "errors": errors, "proposal": proposal, "auto_learned": False,
            "verified": False,
        }

        # Durable automatic learning is limited to corroborated, low-risk facts.
        # Code, permissions, policies and executable behavior are never learned from web text.
        safe = (
            auto
            and len(sources) >= 2
            and len(proposal.get("agreements", [])) >= 1
            and float(proposal.get("confidence", 0)) >= .45
            and not any("conflict" in str(x).lower() for x in proposal.get("issues", []))
            and not any("insufficient" in str(x).lower() for x in proposal.get("issues", []))
            and not any("weak_source_relevance" in str(x).lower() for x in proposal.get("issues", []))
        )
        if safe:
            # Automatic web learning is still forced through the normal gate bypass
            # context; the bypass is scoped to this already-corrobated, low-risk bundle.
            with self.runtime.learning_gate.bypass():
                applied = self.runtime._apply_trusted_knowledge(proposal)
            result["auto_learned"] = bool(applied.get("stored"))
            result["verified"] = bool(applied.get("stored")) and not bool(applied.get("duplicate"))
            if result["auto_learned"]:
                self.state["learned"] += len(proposal.get("agreements", []))
        else:
            gated = self.runtime.learning_gate.request(
                "trusted_knowledge.bootstrap", proposal,
                f"بازبینی یادگیری اینترنتی درباره «{topic}»"
            )
            result["review"] = gated or proposal

        self.state["cycles"] += 1
        self.state["last"] = {
            "topic": topic, "sources": len(sources),
            "agreements": len(proposal.get("agreements", [])),
            "auto_learned": result["auto_learned"],
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save()
        self.runtime.events.emit("internet_learning_cycle", {
            "topic": topic, "sources": len(sources),
            "agreements": len(proposal.get("agreements", [])),
            "auto_learned": result["auto_learned"],
        })
        return result

    def learn_batch(self, topics, max_topics=5, auto=True):
        """Run several bounded low-risk learning cycles and keep failures isolated."""
        results=[]
        seen=set()
        topics=list(topics or [])
        for topic in topics:
            key=str(topic).strip().lower()
            if not key or key in seen or len(results) >= int(max_topics):
                continue
            seen.add(key)
            try:
                results.append(self.learn(str(topic), auto=auto))
            except Exception as exc:
                results.append({"ok":False,"topic":str(topic),"reason":"cycle_error","error":str(exc)[:300]})
        self.state["batch_cycles"] = int(self.state.get("batch_cycles",0)) + len(results)
        self.state["successful_cycles"] = int(self.state.get("successful_cycles",0)) + sum(bool(x.get("auto_learned")) for x in results)
        self._save()
        return {"ok":True,"requested":len(topics),"processed":len(results),"results":results,
                "learned":sum(bool(x.get("auto_learned")) for x in results)}

    def status(self):
        return {
            **self.state,
            "internet_enabled": bool(self.runtime.internet_access.status().get("enabled")),
            "mode": "automatic_low_risk_verified_learning",
        }
