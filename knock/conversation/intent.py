from knock.core.events import VisitorEvent
from knock.providers.llm.base import IntentProvider


class IntentClassifier:
    def __init__(self, provider: IntentProvider) -> None:
        self.provider = provider

    def classify(self, event: VisitorEvent) -> str:
        return self.provider.classify_intent(event.text)
