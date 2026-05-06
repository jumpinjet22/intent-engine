from knock.providers.llm.base import IntentProvider


class MockIntentProvider(IntentProvider):
    def name(self) -> str:
        return "mock-intent"

    def classify_intent(self, text: str) -> str:
        lowered = text.lower()
        if any(k in lowered for k in ("package", "delivery", "amazon", "ups", "fedex")):
            return "delivery"
        if any(k in lowered for k in ("help", "fire", "emergency", "ambulance", "911")):
            return "emergency"
        if any(k in lowered for k in ("hi", "hello", "hey")):
            return "greeting"
        return "unknown"
