from abc import abstractmethod

from knock.providers.base import Provider


class IntentProvider(Provider):
    @abstractmethod
    def classify_intent(self, text: str) -> str:
        raise NotImplementedError
