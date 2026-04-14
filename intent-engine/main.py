#!/usr/bin/env python3
"""Doorbell intent engine entrypoint."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config import Config
from dialogue import DialogueManager
from intent import IntentClassifier
from mqtt import AuthenticatedMQTTClient
from state_machine import SessionState, StateMachine
from runtime_config import apply_runtime_to_env, load_runtime_config
from talkback import TalkbackDriver


logger = logging.getLogger(__name__)


class DoorbellService:
    def __init__(self, config: Config):
        self.config = config
        self.mqtt = AuthenticatedMQTTClient(config)
        self.mqtt.client.on_message = self._on_message
        self.mqtt.set_on_connected(self._on_connected)

        self.state_machine = StateMachine(self._publish_state)
        self.intent_classifier = IntentClassifier(config)
        self.dialogue = DialogueManager(config.clarification_max)
        self.talkback = TalkbackDriver(config, self.mqtt)

        self.last_transcript: str = ""
        self.last_intent: Dict[str, Any] = {}
        self.last_tts_request_id: Optional[str] = None
        self.human_active: bool = False

    def start(self) -> None:
        self._configure_logging()
        self.mqtt.connect()
        self._publish_state(SessionState.IDLE, "startup")

    def shutdown(self) -> None:
        self._publish_state(SessionState.IDLE, "shutdown")
        self.mqtt.disconnect()

    def _configure_logging(self) -> None:
        logging.basicConfig(
            level=self.config.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    def _on_connected(self, client) -> None:
        topics = [
            self.config.mqtt_topic_frigate,
            self.config.mqtt_topic_doorbell_press,
            self.config.mqtt_topic_human_active,
            self.config.mqtt_topic_dialogue_answer,
            self.config.mqtt_topic_tts_request,
        ]
        for topic in topics:
            client.subscribe(topic)
            logger.info("Subscribed to MQTT topic", extra={"topic": topic})

    def _on_message(self, client, userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8")) if msg.payload else {}
            if msg.topic == self.config.mqtt_topic_human_active:
                self._handle_human_active(payload)
                return

            if msg.topic == self.config.mqtt_topic_dialogue_answer:
                self._handle_dialogue_answer(payload)
                return

            if msg.topic == self.config.mqtt_topic_tts_request:
                self.talkback.handle_tts_request(payload)
                return

            if msg.topic in {self.config.mqtt_topic_frigate, self.config.mqtt_topic_doorbell_press}:
                self._handle_trigger(payload, source=msg.topic)
                return
        except json.JSONDecodeError:
            logger.warning("Invalid JSON payload", extra={"topic": msg.topic})
        except Exception as exc:
            logger.exception("Unhandled MQTT processing error", extra={"topic": msg.topic, "error": str(exc)})

    def _handle_human_active(self, payload: Dict[str, Any]) -> None:
        active = bool(payload.get("active", False))
        ttl_s = int(payload.get("ttl_s", 120))
        self.human_active = active
        self.talkback.set_human_active(active)
        if active:
            self.state_machine.transition(SessionState.HUMAN_HANDLING, f"human_override ttl_s={ttl_s}")
            self.talkback.cancel_all()
        else:
            self.state_machine.transition(SessionState.IDLE, "human_override_cleared")

    def _handle_trigger(self, payload: Dict[str, Any], source: str) -> None:
        self.dialogue.reset()
        self.state_machine.transition(SessionState.RINGING, "doorbell_triggered")
        transcript = self._extract_transcript(payload)
        self.last_transcript = transcript

        if self.human_active:
            self.state_machine.transition(SessionState.HUMAN_HANDLING, "human_override")
            return

        self.state_machine.transition(SessionState.AI_HANDLING, "processing")
        if self._contains_safety_keywords(transcript):
            self._escalate("safety_keyword", transcript, intent_guess="emergency", confidence=1.0)
            return

        if self._visitor_requested_human(transcript):
            self._escalate("visitor_requested_human", transcript, intent_guess="unknown", confidence=0.4)
            return

        intent_result = self.intent_classifier.classify(transcript, {"source": source})
        self.last_intent = intent_result
        self._publish_intent(intent_result)

        confidence = float(intent_result.get("confidence", 0.0))
        if confidence >= self.config.confidence_auto_handle:
            self._handle_intent(intent_result)
            return

        if confidence >= self.config.confidence_clarify and self.dialogue.should_clarify(confidence):
            self.state_machine.transition(SessionState.CLARIFYING, "needs_clarification")
            question = self.dialogue.build_clarification_question()
            self._publish_tts_request(question, priority="ai")
            return

        self._escalate("low_confidence", transcript, intent_guess=intent_result.get("intent", "unknown"), confidence=confidence)

    def _handle_dialogue_answer(self, payload: Dict[str, Any]) -> None:
        if self.state_machine.state != SessionState.CLARIFYING:
            return
        answer = str(payload.get("answer", "")).strip()
        resolved = self.dialogue.resolve_from_answer(answer)
        if resolved:
            self._handle_intent({"intent": resolved, "confidence": 0.7, "entities": {}, "suggested_actions": []})
            return

        if self.dialogue.should_clarify(0.6):
            question = self.dialogue.build_clarification_question()
            self._publish_tts_request(question, priority="ai")
            return

        self._escalate("clarification_failed", self.last_transcript, intent_guess="unknown", confidence=0.4)

    def _handle_intent(self, intent_result: Dict[str, Any]) -> None:
        intent = intent_result.get("intent", "unknown")
        response = _response_for_intent(intent)
        if intent == "emergency":
            self._escalate("emergency", self.last_transcript, intent_guess=intent, confidence=1.0)
            return
        self._publish_tts_request(response, priority="ai")
        self.state_machine.transition(SessionState.COOLDOWN, "response_sent")

    def _publish_state(self, state: SessionState, reason: str) -> None:
        self.mqtt.publish(
            self.config.mqtt_topic_session_state,
            {"state": state.value, "reason": reason, "ts": _iso_ts()},
        )

    def _publish_intent(self, intent_result: Dict[str, Any]) -> None:
        payload = {
            "intent": intent_result.get("intent", "unknown"),
            "confidence": float(intent_result.get("confidence", 0.0)),
            "entities": intent_result.get("entities", {}),
            "ts": _iso_ts(),
        }
        self.mqtt.publish(self.config.mqtt_topic_intent, payload)

    def _publish_tts_request(self, text: str, priority: str) -> None:
        if self.human_active:
            return
        request_id = _request_id()
        self.last_tts_request_id = request_id
        self.mqtt.publish(
            self.config.mqtt_topic_tts_request,
            {"text": text, "priority": priority, "request_id": request_id, "ts": _iso_ts()},
        )

    def _escalate(self, reason: str, transcript: str, intent_guess: str, confidence: float) -> None:
        self.state_machine.transition(SessionState.ESCALATED, reason)
        self.mqtt.publish(
            self.config.mqtt_topic_escalate,
            {
                "reason": reason,
                "summary": "Escalated to human",
                "last_transcript": transcript,
                "intent_guess": intent_guess,
                "confidence": confidence,
                "ts": _iso_ts(),
            },
        )

    def _extract_transcript(self, payload: Dict[str, Any]) -> str:
        for key in ("transcript", "text", "speech"):
            value = payload.get(key)
            if value:
                return str(value)
        after = payload.get("after") or {}
        if isinstance(after, dict):
            speech = after.get("speech")
            if speech:
                return str(speech)
        return ""

    def _contains_safety_keywords(self, transcript: str) -> bool:
        text = transcript.lower()
        return any(keyword in text for keyword in self.config.safety_keywords)

    def _visitor_requested_human(self, transcript: str) -> bool:
        text = transcript.lower()
        return any(term in text for term in ["human", "homeowner", "owner", "person"])


def _response_for_intent(intent: str) -> str:
    responses = {
        "delivery": "Thanks. You can leave the package by the door.",
        "guest": "Thanks for coming by. I will let the homeowner know you're here.",
        "service": "Thanks. Please wait a moment while I notify the homeowner.",
        "question": "One moment. I will get the homeowner to help with that.",
        "solicitor": "This is a no-soliciting household. Please leave written info if needed.",
        "unknown": "Hello. How can I help you today?",
    }
    return responses.get(intent, responses["unknown"])


def _iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_id() -> str:
    import uuid

    return uuid.uuid4().hex


def main() -> None:
    runtime_config_path = os.getenv("RUNTIME_CONFIG_PATH", "/data/runtime.json")
    runtime = load_runtime_config(runtime_config_path)
    apply_runtime_to_env(runtime)

    try:
        config = Config()
    except ValueError as exc:
        logging.basicConfig(level="ERROR", format="%(asctime)s - %(levelname)s - %(message)s")
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    service = DoorbellService(config)

    def _handle_signal(signum, frame):
        logger.info("Received shutdown signal", extra={"signal": signum})
        service.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    service.start()

    try:
        signal.pause()
    except KeyboardInterrupt:
        service.shutdown()


if __name__ == "__main__":
    main()
