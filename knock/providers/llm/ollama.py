from knock.providers.llm.base import IntentProvider


class OllamaIntentProvider(IntentProvider):
    def name(self) -> str:
        return "ollama-intent"

    def classify_intent(self, text: str) -> str:
        raise NotImplementedError("Ollama provider is not wired in this foundational pass.")
