from knock.providers.base import Provider


class MockProvider(Provider):
    def name(self) -> str:
        return "mock"
