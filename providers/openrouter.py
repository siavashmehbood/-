"""OpenRouter provider for IRAN learning validation."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from typing import Any

class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = (config or {}).get("openrouter", {})
        self.base_url = str(cfg.get("base_url", "https://openrouter.ai/api/v1")).rstrip("/")
        self.model = str(cfg.get("model", "openrouter/free"))
        self.timeout = int(cfg.get("timeout", 45))
        self.key_name = "OPEN" + "ROUTER_API_KEY"

    def _key(self):
        key = os.environ.get(self.key_name, "").strip()
        if key:
            return key
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                value, _ = winreg.QueryValueEx(h, self.key_name)
                return str(value).strip()
        except Exception:
            return ""

    @staticmethod
    def _parse(raw):
        text = str(raw or "").strip()
        if text.startswith("```"):
            parts = text.split("\\n", 1)
            text = parts[1] if len(parts) == 2 else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        import re
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def generate(self, messages, **kwargs):
        key = os.environ.get(self.key_name, "").strip()
        if not key:
            raise RuntimeError("openrouter_api_key_missing")
        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": 0,
            "max_tokens": int(kwargs.get("max_tokens", 120)),
        }
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "HTTP-Referer": "https://openrouter.ai/",
                "X-Title": "IRAN Cognitive Architecture",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"openrouter_http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("openrouter_network_error") from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("openrouter_empty_response")
        return str((choices[0].get("message") or {}).get("content", "")).strip()

    def validate(self, candidate, domain="general"):
        key = self._key()
        if not key:
            return {"decision": "ERROR", "reason": "api_key_missing"}
        prompt = ("Decide whether this learning candidate is useful and reasonable for IRAN. "
                  "Return ONLY JSON with decision LEARN or REJECT and a short reason. "
                  "Do not apply learning. "
                  f"Domain: {domain}. Candidate: {candidate}")
        payload = {"model": self.model, "messages": [
            {"role": "system", "content": "Return only JSON with decision LEARN or REJECT and a short reason."},
            {"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 120,
            "usage": {"include": True}}
        request = urllib.request.Request(self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return {"decision": "ERROR", "reason": f"http_{exc.code}"}
        except urllib.error.URLError:
            return {"decision": "ERROR", "reason": "network_error"}
        raw = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")).strip()
        parsed = self._parse(raw)
        meta = {"model": data.get("model"), "usage": data.get("usage")}
        if not isinstance(parsed, dict):
            return {"decision": "ERROR", "reason": "invalid_json", **meta}
        decision = str(parsed.get("decision", "")).upper()
        if decision not in {"LEARN", "REJECT"}:
            return {"decision": "ERROR", "reason": "invalid_decision", **meta}
        return {"decision": decision, "reason": str(parsed.get("reason", ""))[:500], **meta}

    def health(self):
        key = bool(os.environ.get(self.key_name, "").strip())
        return {"provider": self.name, "ok": key, "authenticated": key, "model": self.model}
