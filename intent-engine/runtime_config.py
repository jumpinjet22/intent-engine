"""Runtime configuration helpers for environment overlay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_runtime_config(path: str) -> Dict[str, Any]:
    """Load runtime JSON config from disk, returning an empty dict on errors."""
    try:
        contents = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}

    try:
        parsed = json.loads(contents)
    except json.JSONDecodeError:
        return {}

    if not isinstance(parsed, dict):
        return {}

    return parsed


def apply_runtime_to_env(runtime: Dict[str, Any]) -> None:
    """Map supported runtime fields into environment variables when not already set."""
    import os

    runtime_to_env = {
        "mqtt_host": "MQTT_HOST",
        "mqtt_port": "MQTT_PORT",
    }

    for runtime_key, env_key in runtime_to_env.items():
        value = runtime.get(runtime_key)
        if value is None:
            continue
        if os.getenv(env_key) is not None:
            continue
        os.environ[env_key] = str(value)
