"""Simple state machine for doorbell sessions."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional


class SessionState(str, Enum):
    IDLE = "IDLE"
    RINGING = "RINGING"
    AI_HANDLING = "AI_HANDLING"
    CLARIFYING = "CLARIFYING"
    ESCALATED = "ESCALATED"
    HUMAN_HANDLING = "HUMAN_HANDLING"
    COOLDOWN = "COOLDOWN"


class StateMachine:
    def __init__(self, publish_fn: Callable[[SessionState, str], None]):
        self._state = SessionState.IDLE
        self._publish = publish_fn
        self._reason: Optional[str] = None

    @property
    def state(self) -> SessionState:
        return self._state

    def transition(self, new_state: SessionState, reason: str) -> None:
        self._state = new_state
        self._reason = reason
        self._publish(new_state, reason)
