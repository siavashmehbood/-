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

    def health(self):
        key = bool(os.environ.get(self.key_name, "").strip())
        return {"provider": self.name, "ok": key, "authenticated": key, "model": self.model}
