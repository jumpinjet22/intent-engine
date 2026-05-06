import argparse

from knock.conversation.intent import IntentClassifier
from knock.conversation.policy import PolicyEngine
from knock.core.events import VisitorEvent
from knock.core.orchestrator import Orchestrator
from knock.core.state import ConversationContext
from knock.providers.llm.mock import MockIntentProvider


def run_cli() -> None:
    classifier = IntentClassifier(provider=MockIntentProvider())
    orchestrator = Orchestrator(classifier=classifier, policy=PolicyEngine())
    context = ConversationContext()

    print("KNOCK local CLI. Type 'exit' to quit.")
    while True:
        text = input("Visitor: ").strip()
        if text.lower() in {"exit", "quit"}:
            break
        decision = orchestrator.handle_event(VisitorEvent(text=text), context)
        print(f"KNOCK: {decision.message}")
        if decision.escalate:
            print("[Escalation triggered]")


def main() -> None:
    parser = argparse.ArgumentParser(description="KNOCK")
    parser.add_argument("--cli", action="store_true", help="Run local CLI mode")
    args = parser.parse_args()

    if args.cli:
        run_cli()


if __name__ == "__main__":
    main()
