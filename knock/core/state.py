from dataclasses import dataclass, field

from knock.core.session import Session


@dataclass
class ConversationContext:
    session: Session = field(default_factory=Session)
    last_intent: str = "unknown"
