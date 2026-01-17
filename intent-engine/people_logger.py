"""People/event logging helper.

Goal: capture enough artifacts (event id + snapshot + metadata) so you can
later decide what to do (notify, label faces in Frigate, build a dataset, etc.).

This is intentionally conservative: it logs *events* and optionally downloads
snapshots/thumbnails from Frigate. Any face recognition / labeling stays an
explicit opt-in workflow.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import requests


@dataclass
class PeopleLoggerConfig:
    enabled: bool
    log_dir: Path
    frigate_url: str
    frigate_api_key: str = ""
    save_snapshot: bool = True
    save_thumbnail: bool = False


class PeopleLogger:
    def __init__(self, cfg: PeopleLoggerConfig):
        self.cfg = cfg
        if self.cfg.enabled:
            self.cfg.log_dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> Dict[str, str]:
        # Frigate supports auth; many users run it behind a reverse proxy w/ headers.
        # If you set FRIGATE_API_KEY, we send it as "Authorization: Bearer ...".
        # (If your setup is different, just leave empty and handle auth at the proxy.)
        if not self.cfg.frigate_api_key:
            return {}
        return {"Authorization": f"Bearer {self.cfg.frigate_api_key}"}

    def log_event(self, *, session_id: str, event_id: Optional[str], camera: str, intent: str, transcript: str, intent_payload: Dict[str, Any], context: Dict[str, Any]) -> None:
        """Write a JSON metadata file + optionally download snapshot/thumbnail."""
        if not self.cfg.enabled:
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"{ts}_{camera}_{session_id}"
        out_dir = self.cfg.log_dir / ts[:8]
        out_dir.mkdir(parents=True, exist_ok=True)

        meta_path = out_dir / f"{base}.json"
        meta = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_id": event_id,
            "camera": camera,
            "intent": intent,
            "transcript": transcript,
            "intent_payload": intent_payload,
            "context": context,
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        if event_id and self.cfg.save_snapshot:
            self._download_binary(
                url=f"{self.cfg.frigate_url}/api/events/{event_id}/snapshot.jpg",
                dest=out_dir / f"{base}_snapshot.jpg",
            )

        if event_id and self.cfg.save_thumbnail:
            # Newer Frigate versions expose thumbnails via /api/events/:event_id/thumbnail.jpg
            self._download_binary(
                url=f"{self.cfg.frigate_url}/api/events/{event_id}/thumbnail.jpg",
                dest=out_dir / f"{base}_thumbnail.jpg",
            )

    def _download_binary(self, *, url: str, dest: Path) -> None:
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            if r.status_code != 200:
                return
            dest.write_bytes(r.content)
        except Exception:
            # Best effort only
            return
