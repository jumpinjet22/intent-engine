from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "intent-engine"))

from session_state import ALLOWED_TRANSITIONS, ConversationState, can_transition


def test_lifecycle_core_path_is_allowed():
    assert can_transition(ConversationState.IDLE, ConversationState.TRIGGERED)
    assert can_transition(ConversationState.TRIGGERED, ConversationState.CONTEXT_READY)
    assert can_transition(ConversationState.CONTEXT_READY, ConversationState.RESPONDING)
    assert can_transition(ConversationState.RESPONDING, ConversationState.COMPLETED)


def test_terminal_states_have_no_outbound_transitions():
    assert ALLOWED_TRANSITIONS[ConversationState.COMPLETED] == set()
    assert ALLOWED_TRANSITIONS[ConversationState.ABORTED] == set()
    assert ALLOWED_TRANSITIONS[ConversationState.ESCALATED] == set()


def test_invalid_transition_blocked():
    assert not can_transition(ConversationState.IDLE, ConversationState.RESPONDING)
