from abc import ABC, abstractmethod
from typing import Any

class ModelProvider(ABC):
    """Stable interface between Iran's cognitive core and model backends."""

    name = 'unknown'

    @abstractmethod
    def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        raise NotImplementedError

    def health(self) -> dict[str, Any]:
        return {'provider': self.name, 'ok': True}

    def close(self) -> None:
        pass
