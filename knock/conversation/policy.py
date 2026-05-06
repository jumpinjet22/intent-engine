from knock.core.events import VisitorEvent


BLOCKED_KEYWORDS = {
    "home_status": ("home", "anyone there", "is someone home", "is anybody home"),
    "schedule": ("schedule", "when will", "what time", "be back"),
    "unlock": ("unlock", "open the door", "let me in", "buzz me in"),
    "private": ("phone number", "email", "where do you work", "family name"),
}

EMERGENCY_KEYWORDS = ("help", "emergency", "fire", "ambulance", "911", "urgent")


class PolicyEngine:
    def precheck(self, event: VisitorEvent) -> tuple[bool, str | None]:
        text = event.text.lower()
        for reason, keywords in BLOCKED_KEYWORDS.items():
            if any(k in text for k in keywords):
                return False, reason
        return True, None

    def should_escalate(self, event: VisitorEvent) -> bool:
        text = event.text.lower()
        return any(k in text for k in EMERGENCY_KEYWORDS)

    def enforce_short(self, message: str) -> str:
        return message.strip()[:120]
