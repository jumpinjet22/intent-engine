from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Session:
    session_id: str = "local"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turns: int = 0
