from knock.providers.output.base import OutputProvider


class ConsoleOutputProvider(OutputProvider):
    def name(self) -> str:
        return "console"

    def send(self, message: str) -> None:
        print(message)
