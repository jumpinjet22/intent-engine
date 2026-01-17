"""UniFi Protect Integration API handler (no pyunifiprotect).

This intentionally uses only HTTP requests + ffmpeg.

Why:
 - pyunifiprotect is no longer available on PyPI in some environments.
 - We only need a small subset: discover RTSP(S), grab snapshots (optional),
   and create a talkback session so we can play audio to the doorbell speaker.

Config expectations (see config.py):
 - PROTECT_BASE_URL like: https://192.168.1.1/proxy/protect/integration/v1
 - PROTECT_API_KEY: Protect integration API key
 - PROTECT_CAMERA_ID: camera id string
 - PROTECT_VERIFY_SSL: usually false for local IPs w/ self-signed certs

Notes:
 - Talkback session returns an RTP URL + codec info.
 - We encode to Opus and stream via RTP with ffmpeg.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import requests

from config import Config

logger = logging.getLogger(__name__)


class ProtectIntegrationHandler:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.cfg.protect_api_key}"})
        self._rtsp_url_cache: Optional[str] = None

    def _url(self, path: str) -> str:
        base = self.cfg.protect_base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    def _req(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", 15)
        kwargs.setdefault("verify", bool(self.cfg.protect_verify_ssl))
        return self.session.request(method, self._url(path), **kwargs)

    def get_rtsp_url(self) -> Optional[str]:
        """Return RTSPS URL for the configured camera (cached)."""
        # UI can override the RTSP URL (and we also support env var fallback)
        if self.cfg.selected_camera_rtsp_url:
            return self.cfg.selected_camera_rtsp_url
        if self._rtsp_url_cache:
            return self._rtsp_url_cache
        if not self.cfg.talkback_enabled:
            return None

        cam_id = self.cfg.selected_protect_camera_id
        r = self._req("GET", f"cameras/{cam_id}/rtsps-stream")
        if r.status_code != 200:
            logger.warning("Protect rtsps-stream failed: %s %s", r.status_code, r.text[:200])
            return None
        data = r.json() if r.content else {}
        quality = (self.cfg.protect_rtsp_quality or "medium").lower().strip()
        url = data.get(quality) or data.get("medium") or data.get("high") or data.get("low")
        if not url:
            return None
        self._rtsp_url_cache = url
        return url

    def create_talkback_session(self) -> Optional[dict]:
        """Create a talkback session and return dict with url/codec/samplingRate/etc."""
        if not self.cfg.talkback_enabled:
            return None
        cam_id = self.cfg.selected_protect_camera_id
        r = self._req("POST", f"cameras/{cam_id}/talkback-session", json={})
        if r.status_code != 200:
            logger.warning("Protect talkback-session failed: %s %s", r.status_code, r.text[:200])
            return None
        try:
            return r.json()
        except Exception:
            return None

    async def play_audio_file(self, audio_path: Path):
        """Play an audio file through Protect talkback (speaker)."""
        tb = self.create_talkback_session()
        if not tb or not tb.get("url"):
            raise RuntimeError("Talkback session not available")

        url = tb["url"]
        codec = (tb.get("codec") or "opus").lower()
        sr = int(tb.get("samplingRate") or 24000)

        if codec != "opus":
            logger.warning("Unexpected talkback codec '%s' (expected opus). Proceeding anyway.", codec)

        # Encode + stream via RTP
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-re",
            "-i",
            str(audio_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sr),
            "-c:a",
            "libopus",
            "-application",
            "voip",
            "-f",
            "rtp",
            url,
        ]
        logger.debug("Talkback ffmpeg cmd: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg talkback failed: {proc.stderr.decode(errors='ignore')[:300]}")

    async def capture_audio(self, duration: int) -> Optional[np.ndarray]:
        """Capture audio from the camera stream for `duration` seconds.

        This captures *audio-only* from the configured RTSP/RTSPS URL.
        Returns int16 numpy array at cfg.audio_sample_rate.
        """
        rtsp_url = self.get_rtsp_url()
        if not rtsp_url:
            logger.warning("No RTSP/RTSPS URL available for audio capture")
            return None

        sr = int(self.cfg.audio_sample_rate)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-i",
                rtsp_url,
                "-t",
                str(int(duration)),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sr),
                str(wav_path),
            ]
            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0:
                logger.warning("ffmpeg capture failed: %s", proc.stderr.decode(errors="ignore")[:300])
                return None

            # Read wav bytes into numpy (soundfile is already a dep)
            import soundfile as sf

            data, _ = sf.read(str(wav_path), dtype="int16")
            if data is None:
                return None
            return np.asarray(data, dtype=np.int16)
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def stream_audio(self, audio_data: np.ndarray):
        """Stream raw audio to talkback. (Currently: write temp WAV then play)."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
        try:
            import soundfile as sf

            sf.write(str(wav_path), audio_data, self.cfg.audio_sample_rate)
            await self.play_audio_file(wav_path)
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass

    async def cleanup(self):
        try:
            self.session.close()
        except Exception:
            pass
