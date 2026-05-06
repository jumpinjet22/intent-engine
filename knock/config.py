from dataclasses import dataclass


@dataclass
class KnockConfig:
    """Minimal runtime config for local CLI usage."""

    keep_responses_short: bool = True
    emergency_escalation_enabled: bool = True
