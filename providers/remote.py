"""Remote validation provider for IRAN."""
from __future__ import annotations
import json, os, urllib.error, urllib.request

class RemoteProvider:
    name = "remote-validator"

    def __init__(self, config=None):
        self.base_url = "https://openrouter.ai/api/v1"
        self.model = "openrouter/free"
        self.timeout = 45

    def generate(self, messages, **kwargs):
        key = os.environ.get("OPEN"+"ROUTER_API_KEY", "").strip()
        if not key:
            raise RuntimeError("remote_api_key_missing")
        payload = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": 120}
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"remote_http_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("remote_network_error") from exc
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("remote_empty_response")
        return str((choices[0].get("message") or {}).get("content", "")).strip()

    def health(self):
        ok = bool(os.environ.get("OPEN"+"ROUTER_API_KEY", "").strip())
        return {"provider": self.name, "ok": ok, "authenticated": ok}
