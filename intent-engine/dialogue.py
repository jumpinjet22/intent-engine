"""Dialogue manager for clarification and escalation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClarificationState:
    attempts: int = 0
    last_intent: str = "unknown"
    last_transcript: str = ""


class DialogueManager:
    def __init__(self, max_attempts: int):
        self.max_attempts = max_attempts
        self.state = ClarificationState()

    def reset(self) -> None:
        self.state = ClarificationState()

    def should_clarify(self, confidence: float) -> bool:
        return self.state.attempts < self.max_attempts

    def build_clarification_question(self) -> str:
        self.state.attempts += 1
        return (
            "Are you here for a delivery, a guest visit, or service? "
            "Please say: delivery, guest, or service."
        )

    def resolve_from_answer(self, answer: str) -> Optional[str]:
        if not answer:
            return None
        normalized = answer.lower()
        if "delivery" in normalized or "package" in normalized:
            return "delivery"
        if "guest" in normalized or "friend" in normalized or "family" in normalized:
            return "guest"
        if "service" in normalized or "repair" in normalized or "maintenance" in normalized:
            return "service"
        if "emergency" in normalized or "police" in normalized or "fire" in normalized:
            return "emergency"
        return None
