from abc import ABC, abstractmethod


class Provider(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError
