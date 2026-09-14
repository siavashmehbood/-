import json
import os
import urllib.request
import urllib.error

from .base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):
    """Optional real LLM backend using an OpenAI-compatible chat endpoint."""

    name = 'openai-compatible'

    def __init__(self, config):
        model = config.get('model', {})
        self.endpoint = os.getenv('IRAN_MODEL_ENDPOINT', model.get('endpoint', 'https://api.openai.com/v1/chat/completions'))
        self.model = os.getenv('IRAN_MODEL_NAME', model.get('name', 'gpt-5.6'))
        self.api_key = os.getenv('IRAN_MODEL_API_KEY', '')
        self.timeout = int(model.get('timeout', 60))

    def generate(self, messages, **kwargs):
        if not self.api_key:
            raise RuntimeError('IRAN_MODEL_API_KEY is not configured')
        payload = {'model': self.model, 'messages': messages}
        payload.update({k: v for k, v in kwargs.items() if k in {'temperature', 'max_tokens'}})
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'model HTTP {exc.code}: {detail[:500]}') from exc
        return data['choices'][0]['message']['content']

    def health(self):
        return {
            'provider': self.name,
            'ok': bool(self.api_key),
            'mode': 'remote-llm',
            'model': self.model,
            'endpoint': self.endpoint,
        }
