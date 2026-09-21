"""Compatibility facade; networking belongs exclusively to ProviderManager.

Legacy model.provider=openrouter still starts a local answering runtime. Callers
of validate must attach the runtime's reviewer_manager to use controlled review.
"""
from .iran import IranProvider


class OpenRouterProvider(IranProvider):
    def __init__(self, config=None, reviewer_manager=None):
        super().__init__()
        self.reviewer_manager = reviewer_manager

    def validate(self, candidate, domain='general'):
        if self.reviewer_manager is None:
            return {'decision': 'ERROR', 'reason': 'reviewer_manager_not_configured'}
        reviewed = self.reviewer_manager.review({'candidate': candidate, 'domain': domain})
        if not reviewed.get('ok'):
            return {'decision': 'ERROR', 'reason': reviewed.get('reason', 'unavailable')}
        result = reviewed['result']
        return {'decision': 'LEARN' if result['learn'] else 'REJECT',
                'reason': result.get('reason', ''), 'provider': result.get('provider'),
                'model': result.get('model')}
