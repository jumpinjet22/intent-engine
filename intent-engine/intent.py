"""Intent classification for doorbell transcripts."""

from __future__ import annotations

import json
import logging
from typing import Dict

import requests
from tenacity import retry, stop_after_attempt, wait_fixed

from config import Config

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self, config: Config):
        self.config = config

    def classify(self, transcript: str, context: Dict) -> Dict:
        if not transcript:
            return {"intent": "unknown", "confidence": 0.0, "entities": {}, "suggested_actions": []}

        if not self.config.llm_enabled:
            return self._heuristic_intent(transcript)

        try:
            return self._llm_intent(transcript, context)
        except Exception as exc:
            logger.warning("LLM intent classification failed", extra={"error": str(exc)})
            return self._heuristic_intent(transcript)

    def _heuristic_intent(self, transcript: str) -> Dict:
        text = transcript.lower()
        if any(k in text for k in ["delivery", "package", "ups", "fedex", "amazon"]):
            return {"intent": "delivery", "confidence": 0.6, "entities": {}, "suggested_actions": []}
        if any(k in text for k in ["appointment", "meeting", "here to see", "guest"]):
            return {"intent": "guest", "confidence": 0.6, "entities": {}, "suggested_actions": []}
        if any(k in text for k in ["service", "repair", "maintenance", "utility"]):
            return {"intent": "service", "confidence": 0.6, "entities": {}, "suggested_actions": []}
        if any(k in text for k in ["police", "fire", "emergency"]):
            return {"intent": "emergency", "confidence": 0.9, "entities": {}, "suggested_actions": ["handoff"]}
        return {"intent": "unknown", "confidence": 0.4, "entities": {}, "suggested_actions": []}

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(0.5), reraise=True)
    def _llm_intent(self, transcript: str, context: Dict) -> Dict:
        prompt = _build_prompt(transcript, context)
        response = requests.post(
            f"{self.config.ollama_host}/api/generate",
            json={
                "model": self.config.llm_model,
                "prompt": prompt,
                "stream": False,
            },
            timeout=self.config.llm_timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        text = (data.get("response") or "").strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Invalid LLM response")
        return parsed


def _build_prompt(transcript: str, context: Dict) -> str:
    ctx = ", ".join([f"{k}={v}" for k, v in (context or {}).items() if v is not None])
    return f"""You are an intent classifier for a doorbell assistant.

You MUST output ONLY valid JSON. No prose. No markdown. No code fences.

Allowed intents:
- delivery (packages, FedEx/UPS/USPS/Amazon, courier)
- guest (friend/family/appointment/expected visitor)
- service (repair, contractor, maintenance, utility worker)
- solicitor (sales, fundraising, political, religious solicitation)
- question (asking hours, directions, general info)
- emergency (police/fire/medical, urgent)
- unknown (anything else)

Context: {ctx or "(none)"}
Visitor said: "{transcript}"

Return JSON with EXACT keys:
{{
  "intent": "one of the allowed intents",
  "confidence": 0.0,
  "entities": {{"name": "", "company": "", "tracking": "", "appointment_time": ""}},
  "suggested_actions": ["short action strings"]
}}
"""
