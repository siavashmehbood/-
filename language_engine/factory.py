"""Build the subordinate local language engine from explicit runtime configuration."""
from __future__ import annotations
from .engine import IranLanguageEngine
from .backends.local_http import LocalHTTPBackend


def create_language_engine(config):
    cfg=dict((config or {}).get("language_engine") or {})
    if not cfg.get("enabled",False):
        return None
    backend=str(cfg.get("backend","local_http")).strip().lower()
    if backend!="local_http":
        raise ValueError("unsupported language_engine backend")
    model=str(cfg.get("model","")).strip()
    if not model:
        raise ValueError("language_engine.model is required when enabled")
    endpoint=str(cfg.get("endpoint","http://127.0.0.1:8000/v1/chat/completions"))
    timeout=float(cfg.get("timeout",120))
    return IranLanguageEngine(LocalHTTPBackend(model=model,endpoint=endpoint,timeout=timeout))
