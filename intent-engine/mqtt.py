"""Authenticated MQTT client wrapper with reconnect and will message."""

from __future__ import annotations

import json
import logging
from typing import Callable, Optional

import paho.mqtt.client as mqtt

from config import Config

logger = logging.getLogger(__name__)


class AuthenticatedMQTTClient:
    def __init__(self, config: Config):
        self.config = config
        self.client = mqtt.Client(client_id=config.resolved_client_id, clean_session=True)
        self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        if config.mqtt_tls_enabled:
            self.client.tls_set(ca_certs=config.mqtt_tls_ca_cert or None)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = None
        self._on_connected: Optional[Callable[[mqtt.Client], None]] = None

        will_payload = json.dumps({"state": "OFFLINE", "reason": "will_disconnect", "ts": _iso_ts()})
        self.client.will_set(config.mqtt_topic_session_state, will_payload, qos=1, retain=False)

    def set_on_connected(self, handler: Callable[[mqtt.Client], None]) -> None:
        self._on_connected = handler

    def connect(self) -> None:
        logger.info(
            "Connecting to MQTT broker",
            extra={
                "mqtt_host": self.config.mqtt_host,
                "mqtt_port": self.config.mqtt_port,
                "mqtt_tls": self.config.mqtt_tls_enabled,
                "mqtt_client_id": self.config.resolved_client_id,
                "mqtt_username_set": bool(self.config.mqtt_username),
            },
        )
        self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=60)
        self.client.loop_start()

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: dict, *, qos: int = 0, retain: bool = False) -> None:
        try:
            self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
        except Exception as exc:
            logger.warning("Failed to publish MQTT payload", extra={"topic": topic, "error": str(exc)})

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected", extra={"mqtt_host": self.config.mqtt_host, "mqtt_port": self.config.mqtt_port})
            if self._on_connected:
                self._on_connected(client)
        else:
            logger.error("MQTT connection failed", extra={"result_code": rc})

    def _on_disconnect(self, client, userdata, rc):
        logger.warning("MQTT disconnected", extra={"result_code": rc})


def _iso_ts() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
