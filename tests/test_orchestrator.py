from knock.conversation.intent import IntentClassifier
from knock.conversation.policy import PolicyEngine
from knock.core.events import VisitorEvent
from knock.core.orchestrator import Orchestrator
from knock.providers.llm.mock import MockIntentProvider


def _orchestrator() -> Orchestrator:
    return Orchestrator(IntentClassifier(MockIntentProvider()), PolicyEngine())


def test_delivery_intent() -> None:
    decision = _orchestrator().handle_event(VisitorEvent(text="Hi, I have an Amazon package."))
    assert decision.intent == "delivery"
    assert "leave the package" in decision.message.lower()
    assert decision.escalate is False


def test_emergency_escalation() -> None:
    decision = _orchestrator().handle_event(VisitorEvent(text="Help, this is an emergency."))
    assert decision.escalate is True
    assert "alerting" in decision.message.lower()


def test_occupancy_schedule_safety() -> None:
    decision = _orchestrator().handle_event(VisitorEvent(text="Is anyone home and when will they be back?"))
    assert decision.blocked_by_policy is True
    assert decision.intent == "blocked"


def test_unknown_visitor_fallback() -> None:
    decision = _orchestrator().handle_event(VisitorEvent(text="Can I ask a random question?"))
    assert decision.intent == "unknown"
    assert "leave a message" in decision.message.lower()
