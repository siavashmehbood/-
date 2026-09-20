from .iran import IranProvider
from .openrouter import OpenRouterProvider


def create_provider(config):
    model = config.get("model", {})
    provider = model.get("provider", "iran").lower()
    if provider in {"iran", "local"}:
        return IranProvider()
    if provider == "openrouter":
        return OpenRouterProvider(config)
    raise ValueError(f"unknown provider: {provider}")
