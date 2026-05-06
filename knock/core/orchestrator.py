from knock.conversation.intent import IntentClassifier
from knock.conversation.policy import PolicyEngine
from knock.conversation.prompts import SAFE_RESPONSES
from knock.core.events import VisitorEvent
from knock.core.responses import ResponseDecision
from knock.core.state import ConversationContext


class Orchestrator:
    def __init__(self, classifier: IntentClassifier, policy: PolicyEngine) -> None:
        self.classifier = classifier
        self.policy = policy

    def handle_event(self, event: VisitorEvent, context: ConversationContext | None = None) -> ResponseDecision:
        context = context or ConversationContext()
        context.session.turns += 1

        allowed, reason = self.policy.precheck(event)
        if not allowed:
            return ResponseDecision(
                message=SAFE_RESPONSES["blocked"],
                intent="blocked",
                blocked_by_policy=True,
                reason=reason,
            )

        intent = self.classifier.classify(event)
        escalate = self.policy.should_escalate(event) or intent == "emergency"
        response_key = "emergency" if escalate else intent
        message = SAFE_RESPONSES.get(response_key, SAFE_RESPONSES["unknown"])
        message = self.policy.enforce_short(message)
        context.last_intent = intent

        return ResponseDecision(message=message, intent=intent, escalate=escalate)
