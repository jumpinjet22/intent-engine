"""Configuration for the doorbell intent engine."""

from __future__ import annotations

import os
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


class Config(BaseModel):
    """Validated configuration for the doorbell intent engine."""

    # Core environment
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "prod"))

    # MQTT configuration (required)
    mqtt_host: str = Field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    mqtt_port: int = Field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    mqtt_username: str = Field(default_factory=lambda: os.getenv("MQTT_USERNAME", ""))
    mqtt_password: str = Field(default_factory=lambda: os.getenv("MQTT_PASSWORD", ""))
    mqtt_client_id: str = Field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID", ""))
    mqtt_tls_enabled: bool = Field(default_factory=lambda: _env_bool("MQTT_TLS_ENABLED", "false"))
    mqtt_tls_ca_cert: Optional[str] = Field(default_factory=lambda: os.getenv("MQTT_TLS_CA_CERT"))

    # Topics (subscribe)
    mqtt_topic_frigate: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_FRIGATE", "frigate/events"))
    mqtt_topic_doorbell_press: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_DOORBELL_PRESS", "doorbell/doorbell_press"))
    mqtt_topic_human_active: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_HUMAN_ACTIVE", "doorbell/human_active"))
    mqtt_topic_dialogue_answer: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_DIALOGUE_ANSWER", "doorbell/dialogue/answer"))

    # Topics (publish)
    mqtt_topic_session_state: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_SESSION_STATE", "doorbell/session/state"))
    mqtt_topic_intent: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_INTENT", "doorbell/intent"))
    mqtt_topic_tts_request: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_TTS_REQUEST", "doorbell/tts/request"))
    mqtt_topic_tts_status: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_TTS_STATUS", "doorbell/tts/status"))
    mqtt_topic_escalate: str = Field(default_factory=lambda: os.getenv("MQTT_TOPIC_ESCALATE", "doorbell/escalate"))

    # Intent/classification configuration
    llm_enabled: bool = Field(default_factory=lambda: _env_bool("LLM_ENABLED", "true"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "llama3.2:3b"))
    ollama_host: str = Field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    llm_timeout_s: int = Field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_S", "8")))

    # Dialogue behavior
    confidence_auto_handle: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_AUTO_HANDLE", "0.75")))
    confidence_clarify: float = Field(default_factory=lambda: float(os.getenv("CONFIDENCE_CLARIFY", "0.5")))
    clarification_max: int = Field(default_factory=lambda: int(os.getenv("CLARIFICATION_MAX", "2")))

    # Safety keywords (comma-separated)
    safety_keywords: List[str] = Field(default_factory=lambda: [
        k.strip().lower()
        for k in os.getenv(
            "SAFETY_KEYWORDS",
            "police,emergency,fire,gas,leak,injury,weapon,warrant,lawsuit,sign,contract",
        ).split(",")
        if k.strip()
    ])

    # Talkback (mock mode)
    talkback_mock_enabled: bool = Field(default_factory=lambda: _env_bool("TALKBACK_MOCK_ENABLED", "true"))

    @model_validator(mode="after")
    def _validate_required(self) -> "Config":
        missing = []
        if not self.mqtt_username:
            missing.append("MQTT_USERNAME")
        if not self.mqtt_password:
            missing.append("MQTT_PASSWORD")
        if missing:
            raise ValueError(f"Missing required MQTT credentials: {', '.join(missing)}")
        return self

    @property
    def resolved_client_id(self) -> str:
        if self.mqtt_client_id:
            return self.mqtt_client_id
        return f"doorbell-engine-{uuid.uuid4().hex[:10]}"
