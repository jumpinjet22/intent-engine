"""Frigate Face Library integration.

This module is intentionally conservative.

Goal:
- ONLY register/train faces when the intent engine explicitly allows it (ex: repeat solicitors).
- Never attempt to label every visitor.

Frigate endpoints used (per Frigate HTTP API docs / swagger):
- GET  /api/events/{event_id}/snapshot.jpg
- POST /api/faces/{name}/register   (multipart form-data, file)
- POST /api/faces/train/{name}/classify  (or similar train mode)

Note: endpoint paths can vary slightly by Frigate version; we keep these configurable
and log failures without breaking the doorbell flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests


@dataclass
class FrigateFaceConfig:
    enabled: bool
    frigate_url: str
    api_key: str = ""
    dry_run: bool = False
    store_dir: Path = Path("/data/faces")

    # Labeling policy
    allowed_intents: Tuple[str, ...] = ("solicitor",)
    min_confidence: float = 0.85
    prefix: str = "solicitor-"
    auto_train: bool = True
    train_mode: str = "classify"  # 'classify' per docs
    name_maxlen: int = 48


class FrigateFaceClient:
    def __init__(self, cfg: FrigateFaceConfig):
        self.cfg = cfg
        if self.cfg.enabled:
            self.cfg.store_dir.mkdir(parents=True, exist_ok=True)

    def _headers(self) -> Dict[str, str]:
        if not self.cfg.api_key:
            return {}
        return {"Authorization": f"Bearer {self.cfg.api_key}"}

    @staticmethod
    def slugify(text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = text.strip("_")
        return text or "unknown"

    def build_name(self, *, label: str) -> str:
        """Build a Frigate face name that is readable and safe."""
        base = self.slugify(label)
        name = f"{self.cfg.prefix}{base}" if self.cfg.prefix else base
        if len(name) > self.cfg.name_maxlen:
            name = name[: self.cfg.name_maxlen].rstrip("_")
        return name

    def _download_snapshot(self, event_id: str, dest: Path) -> bool:
        url = f"{self.cfg.frigate_url}/api/events/{event_id}/snapshot.jpg"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            if r.status_code != 200:
                return False
            dest.write_bytes(r.content)
            return True
        except Exception:
            return False

    def register_face(self, name: str, image_path: Path) -> bool:
        """Register a face image under a given identity name."""
        if not self.cfg.enabled:
            return False
        if self.cfg.dry_run:
            return True

        url = f"{self.cfg.frigate_url}/api/faces/{name}/register"
        try:
            with image_path.open("rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                r = requests.post(url, headers=self._headers(), files=files, timeout=15)
            return r.status_code == 200
        except Exception:
            return False

    def train_face(self, name: str) -> bool:
        """Train the face model for a given identity."""
        if not self.cfg.enabled:
            return False
        if self.cfg.dry_run:
            return True

        # Docs screenshot shows: /api/faces/train/:name/classify
        url = f"{self.cfg.frigate_url}/api/faces/train/{name}/{self.cfg.train_mode}"
        try:
            r = requests.post(url, headers=self._headers(), json={}, timeout=30)
            return r.status_code == 200
        except Exception:
            return False

    def register_from_event(self, *, event_id: str, label: str) -> Optional[str]:
        """Download snapshot for the event and register/train it. Returns the face name on success."""
        if not self.cfg.enabled or not event_id:
            return None

        name = self.build_name(label=label)
        img_path = self.cfg.store_dir / f"{name}__{event_id}.jpg"

        if not self._download_snapshot(event_id, img_path):
            return None

        ok_reg = self.register_face(name, img_path)
        if not ok_reg:
            return None

        if self.cfg.auto_train:
            ok_train = self.train_face(name)
            if not ok_train:
                # Still keep registration; training can be manual later.
                return name

        return name
