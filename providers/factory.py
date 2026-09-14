import os
from .iran import IranProvider
from .remote import OpenAICompatibleProvider


def create_provider(config):
    model=config.get('model',{}); provider=model.get('provider','iran').lower()
    key=os.getenv('IRAN_MODEL_API_KEY','').strip()
    if provider in {'auto','iran'} and key:
        return OpenAICompatibleProvider(config)
    if provider in {'iran','local'}:
        return IranProvider()
    if provider in {'openai','openai-compatible','remote'}:
        return OpenAICompatibleProvider(config)
    raise ValueError(f'Unknown model provider: {provider}')
