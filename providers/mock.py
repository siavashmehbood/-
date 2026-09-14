from .base import ModelProvider

class MockProvider(ModelProvider):
    name = 'mock'

    def generate(self, messages, **kwargs):
        for message in reversed(messages):
            if message.get('role') == 'user':
                return '[MOCK] ' + message.get('content', '')
        return '[MOCK] ready'
