from abc import abstractmethod

from knock.providers.base import Provider


class GenericProvider(Provider):
    @abstractmethod
    def handle(self, payload: str) -> str:
        raise NotImplementedError
