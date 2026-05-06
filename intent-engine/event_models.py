"""Canonical internal event models for orchestration and policy boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_trace_id() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class NormalizedEvent:
    session_id: str
    event_type: str
    source: str
    timestamp: str = field(default_factory=utc_now_iso)
    trace_id: str = field(default_factory=new_trace_id)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionRequest:
    session_id: str
    timestamp: str
    trace_id: str
    context: Dict[str, Any]
    latest_event: NormalizedEvent


@dataclass(frozen=True)
class PolicyDecision:
    session_id: str
    allow_response: bool
    response_mode: str  # auto, llm, clarify, escalate, deny
    reason: str
    hard_constraints: Dict[str, Any] = field(default_factory=dict)
    prompt_profile: Optional[str] = None


@dataclass(frozen=True)
class SessionStateEvent:
    session_id: str
    from_state: str
    to_state: str
    reason: str
    timestamp: str = field(default_factory=utc_now_iso)
    trace_id: str = field(default_factory=new_trace_id)
