from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResponseDecision:
    """What KNOCK should say and whether humans should be alerted."""

    message: str
    intent: str
    escalate: bool = False
    blocked_by_policy: bool = False
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
