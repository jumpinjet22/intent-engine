from knock.providers.output.base import OutputProvider


class MockOutputProvider(OutputProvider):
    def __init__(self) -> None:
        self.sent: list[str] = []

    def name(self) -> str:
        return "mock-output"

    def send(self, message: str) -> None:
        self.sent.append(message)
