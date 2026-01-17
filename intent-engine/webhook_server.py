"""Webhook server for UniFi doorbell ring events and human-ack flow."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request

from config import Config

logger = logging.getLogger(__name__)


class WebhookServer:
    """Flask webhook server that bridges HTTP callbacks into the engine."""

    def __init__(self, config: Config, engine, loop: Optional[asyncio.AbstractEventLoop]):
        self.config = config
        self.engine = engine
        self.loop = loop
        self.app = Flask(__name__)
        self._configure_routes()

    def _configure_routes(self) -> None:
        self.app.add_url_rule(self.config.webhook_path, view_func=self._handle_unifi_webhook, methods=["POST"])
        self.app.add_url_rule(self.config.webhook_human_ack_path, view_func=self._handle_human_ack, methods=["POST"])
        self.app.add_url_rule("/healthz", view_func=self._healthcheck, methods=["GET"])

    def _healthcheck(self):
        return jsonify({"status": "ok"})

    def _authorized(self, payload: Dict[str, Any]) -> bool:
        token = (self.config.webhook_token or "").strip()
        if not token:
            return True

        header_token = request.headers.get("X-Webhook-Token") or request.headers.get("Authorization")
        if header_token and header_token.startswith("Bearer "):
            header_token = header_token.replace("Bearer ", "", 1).strip()

        payload_token = str(payload.get("token", "")).strip()
        return token in {payload_token, (header_token or "").strip()}

    def _extract_event_type(self, payload: Dict[str, Any]) -> str:
        for key in ("event", "type", "eventType", "event_type"):
            value = payload.get(key)
            if value:
                return str(value).strip()
        return ""

    def _handle_unifi_webhook(self):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400
        if not self._authorized(payload):
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        event_type = self._extract_event_type(payload).lower()
        if event_type and event_type not in self.config.webhook_doorbell_event_set:
            return jsonify({"ok": True, "ignored": True, "reason": "event_not_configured"}), 200

        trigger_payload = {
            "source": "unifi_webhook",
            "camera_id": payload.get("camera_id") or payload.get("cameraId") or payload.get("camera"),
            "camera_name": payload.get("camera_name") or payload.get("cameraName") or payload.get("camera"),
            "context": {
                "trigger_type": "doorbell_press",
                "location": payload.get("location") or "front_door",
                "time_of_day": payload.get("time_of_day"),
            },
            "raw": payload,
        }
        self._schedule_trigger(trigger_payload)
        return jsonify({"ok": True, "queued": True})

    def _handle_human_ack(self):
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400
        if not self._authorized(payload):
            return jsonify({"ok": False, "error": "unauthorized"}), 401

        message = payload.get("message") or self.config.human_acknowledgment_text
        if not isinstance(message, str) or not message.strip():
            message = self.config.human_acknowledgment_text

        self._schedule_ack(message.strip(), payload)
        return jsonify({"ok": True, "queued": True})

    def _schedule_trigger(self, payload: Dict[str, Any]) -> None:
        if not self.loop:
            logger.warning("Event loop not set; dropping webhook trigger")
            return

        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(self.engine.handle_trigger_event(payload)))

    def _schedule_ack(self, message: str, payload: Dict[str, Any]) -> None:
        if not self.loop:
            logger.warning("Event loop not set; dropping human ack")
            return

        ack_context = {
            "timestamp": payload.get("timestamp"),
            "source": payload.get("source", "human_ack"),
            "message": message,
        }
        self.loop.call_soon_threadsafe(
            lambda: asyncio.create_task(self.engine.play_human_acknowledgment(message, ack_context))
        )

    def run(self) -> None:
        self.app.run(host=self.config.webhook_host, port=self.config.webhook_port)
