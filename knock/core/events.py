from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class VisitorEvent:
    """Incoming visitor utterance plus optional metadata."""

    text: str
    source: str = "cli"
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
