"""Response template manager.

Keeps spoken responses editable without touching Python code.

Templates live in a YAML file (default: /app/config/templates.yml).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml


@dataclass
class TemplateResult:
    text: str
    template_id: str


class TemplateManager:
    def __init__(self, path: str):
        self.path = path
        self._data: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    def render(self, intent: str, context: Dict[str, Any], intent_result: Dict[str, Any], *, requires_human: bool) -> TemplateResult:
        """Pick and render a template for the intent.

        Rules:
        - If requires_human, prefer the handoff template for that intent (if present), else fall back to global handoff.
        - Otherwise, use the normal intent templates.
        - If intent is missing, fall back to unknown.
        """

        intent = (intent or "unknown").strip().lower() or "unknown"
        templates = (self._data.get("templates") or {})
        globals_ = (self._data.get("globals") or {})

        chosen_bucket = None
        if requires_human:
            chosen_bucket = (templates.get(intent) or {}).get("handoff") or globals_.get("handoff")
        else:
            # If this looks like a repeat offender (e.g. recognized solicitor), prefer a firmer response bucket.
            if bool((context or {}).get("repeat_offender")):
                chosen_bucket = (templates.get(intent) or {}).get("repeat") or (templates.get(intent) or {}).get("responses")
            else:
                chosen_bucket = (templates.get(intent) or {}).get("responses")

        if not chosen_bucket:
            chosen_bucket = (templates.get("unknown") or {}).get("responses") or ["Thanks! One moment please."]

        # Normalize to list
        if isinstance(chosen_bucket, str):
            chosen_bucket = [chosen_bucket]
        if not isinstance(chosen_bucket, list) or not chosen_bucket:
            chosen_bucket = ["Thanks! One moment please."]

        text = random.choice(chosen_bucket)

        # Basic placeholder replacement
        entities = (intent_result or {}).get("entities") or {}
        replace_map = {
            "name": entities.get("name") or "",
            "company": entities.get("company") or "",
            "tracking": entities.get("tracking") or "",
            "time_of_day": (context or {}).get("time_of_day") or "",
            "location": (context or {}).get("location") or "",
            "appointment_time": entities.get("appointment_time") or "",
        }
        for k, v in replace_map.items():
            text = text.replace("{" + k + "}", str(v))

        # Optional AI disclosure
        disclosure = globals_.get("ai_disclosure")
        disclose_mode = str(globals_.get("ai_disclosure_mode", "never")).lower()  # never|handoff_only|always
        if disclosure and disclose_mode in {"always", "handoff_only"}:
            if disclose_mode == "always" or requires_human:
                text = f"{text} {disclosure}".strip()

        return TemplateResult(text=text.strip(), template_id=f"{intent}:{'handoff' if requires_human else 'responses'}")
