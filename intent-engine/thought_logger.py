"""Structured "thought" logging for debugging doorbell sessions.

Writes JSONL (one JSON object per line) so you can tail/grep/jq it easily.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


PHONE_RE = re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str) -> str:
    text = PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    return text


@dataclass
class ThoughtLogger:
    enabled: bool
    path: str
    include_transcript: bool = False
    redact_pii: bool = True

    def __post_init__(self) -> None:
        if not self.enabled:
            return
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def log(self, event: str, session_id: str, **fields: Any) -> None:
        if not self.enabled:
            return

        payload: Dict[str, Any] = {
            "ts": _utc_now(),
            "event": event,
            "session_id": session_id,
            **fields,
        }

        # Gate transcript (and optionally redact sensitive strings)
        if "transcript" in payload and not self.include_transcript:
            payload.pop("transcript", None)

        if self.redact_pii:
            for k in ("transcript", "response_text"):
                if k in payload and isinstance(payload[k], str):
                    payload[k] = _redact(payload[k])

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
