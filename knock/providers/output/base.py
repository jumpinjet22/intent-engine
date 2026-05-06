from abc import abstractmethod

from knock.providers.base import Provider


class OutputProvider(Provider):
    @abstractmethod
    def send(self, message: str) -> None:
        raise NotImplementedError
