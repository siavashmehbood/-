"""Offline-only OpenAI-compatible local model adapter.

The adapter rejects non-loopback endpoints. Tests inject transport so CI never opens
a socket or downloads model weights.
"""
from __future__ import annotations
import json, time, urllib.request
from urllib.parse import urlparse
from language_engine.base import GenerationRequest, GenerationResult


def _loopback(url):
    host=(urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1","localhost","::1"}


class LocalHTTPBackend:
    name="local_http"

    def __init__(self, model, endpoint="http://127.0.0.1:8000/v1/chat/completions",
                 timeout=120, transport=None):
        if not _loopback(endpoint):
            raise ValueError("local language backend endpoint must be loopback-only")
        self.model=str(model); self.endpoint=str(endpoint); self.timeout=float(timeout)
        self.transport=transport or self._post

    def _post(self,payload):
        request=urllib.request.Request(self.endpoint,
            data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json"},method="POST")
        with urllib.request.urlopen(request,timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload={"model":self.model,"messages":list(request.messages),
                 "temperature":request.temperature,"max_tokens":request.max_tokens}
        started=time.monotonic()
        data=self.transport(payload)
        text=data["choices"][0]["message"]["content"]
        elapsed=(time.monotonic()-started)*1000
        usage=data.get("usage",{})
        return GenerationResult(text=str(text),backend=self.name,model=self.model,
            latency_ms=round(elapsed,3),metadata={"offline":True,"usage":usage})
