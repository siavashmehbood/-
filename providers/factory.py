from .iran import IranProvider


def create_provider(config):
    model=config.get('model',{}); provider=model.get('provider','iran').lower()
    if provider in {'iran','local'}:
        return IranProvider()
    raise ValueError('Iran is offline-only; external AI providers are disabled')
