"""Talkback driver that responds to TTS requests."""

from __future__ import annotations

import logging
import threading
from typing import Dict

from config import Config
from mqtt import AuthenticatedMQTTClient

logger = logging.getLogger(__name__)


class TalkbackDriver:
    def __init__(self, config: Config, mqtt_client: AuthenticatedMQTTClient):
        self.config = config
        self.mqtt_client = mqtt_client
        self._lock = threading.Lock()
        self._human_active = False

    def set_human_active(self, active: bool) -> None:
        self._human_active = active

    def handle_tts_request(self, payload: Dict) -> None:
        request_id = payload.get("request_id")
        if self._human_active:
            self._publish_status(request_id, "cancelled", "human_active")
            return
        if not request_id:
            self._publish_status("unknown", "failed", "missing_request_id")
            return

        if not self._lock.acquire(blocking=False):
            self._publish_status(request_id, "busy", "talkback_busy")
            return

        try:
            if self.config.talkback_mock_enabled:
                self._publish_status(request_id, "ok", "mock_playback")
            else:
                self._publish_status(request_id, "failed", "talkback_not_configured")
        finally:
            self._lock.release()

    def cancel_all(self) -> None:
        self._publish_status("unknown", "cancelled", "human_override")

    def _publish_status(self, request_id: str, status: str, detail: str) -> None:
        self.mqtt_client.publish(
            self.config.mqtt_topic_tts_status,
            {
                "request_id": request_id,
                "status": status,
                "detail": detail,
                "ts": _iso_ts(),
            },
        )


def _iso_ts() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
