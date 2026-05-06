"""Session state model and transition validation for the doorbell conversation lifecycle."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class ConversationState(str, Enum):
    IDLE = "IDLE"
    TRIGGERED = "TRIGGERED"
    CONTEXT_READY = "CONTEXT_READY"
    RESPONDING = "RESPONDING"
    LISTENING = "LISTENING"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


ALLOWED_TRANSITIONS: Dict[ConversationState, Set[ConversationState]] = {
    ConversationState.IDLE: {ConversationState.TRIGGERED},
    ConversationState.TRIGGERED: {
        ConversationState.CONTEXT_READY,
        ConversationState.ABORTED,
    },
    ConversationState.CONTEXT_READY: {
        ConversationState.RESPONDING,
        ConversationState.ESCALATED,
        ConversationState.ABORTED,
    },
    ConversationState.RESPONDING: {
        ConversationState.LISTENING,
        ConversationState.COMPLETED,
        ConversationState.ESCALATED,
        ConversationState.ABORTED,
    },
    ConversationState.LISTENING: {
        ConversationState.RESPONDING,
        ConversationState.COMPLETED,
        ConversationState.ESCALATED,
        ConversationState.ABORTED,
    },
    ConversationState.ESCALATED: set(),
    ConversationState.COMPLETED: set(),
    ConversationState.ABORTED: set(),
}


def can_transition(from_state: ConversationState, to_state: ConversationState) -> bool:
    return to_state in ALLOWED_TRANSITIONS[from_state]
