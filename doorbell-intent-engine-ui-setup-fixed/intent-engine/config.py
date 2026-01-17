"""Configuration management for the doorbell intent engine"""

import os
import json
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


_RUNTIME_CACHE = {
    "path": None,
    "mtime": 0.0,
    "data": {},
}


def _load_runtime_config(path: str) -> dict:
    """Load UI-managed runtime config (camera selection, etc.) with a tiny cache."""
    if not path:
        return {}
    try:
        p = Path(path)
        if not p.exists():
            return {}
        mtime = p.stat().st_mtime
        if _RUNTIME_CACHE["path"] == path and _RUNTIME_CACHE["mtime"] == mtime:
            return _RUNTIME_CACHE["data"] or {}
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            data = {}
        _RUNTIME_CACHE.update({"path": path, "mtime": mtime, "data": data})
        return data
    except Exception:
        return {}


class Config(BaseModel):
    """Configuration for the doorbell intent engine"""
    
    # Ollama configuration
    ollama_host: str = Field(default_factory=lambda: os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
    llm_model: str = Field(default_factory=lambda: os.getenv('LLM_MODEL', 'llama3.2:3b'))
    
    # Whisper configuration
    whisper_model: str = Field(default_factory=lambda: os.getenv('WHISPER_MODEL', 'base'))
    whisper_device: str = Field(default='cuda')
    whisper_compute_type: str = Field(default='float16')
    
    # TTS configuration
    tts_engine: str = Field(default_factory=lambda: os.getenv('TTS_ENGINE', 'xtts'))
    tts_voice_sample: Optional[str] = Field(default=None)
    enable_voice_cloning: bool = Field(default_factory=lambda: os.getenv('ENABLE_VOICE_CLONING', 'false').lower() == 'true')
    
    # Audio configuration
    audio_sample_rate: int = Field(default_factory=lambda: int(os.getenv('AUDIO_SAMPLE_RATE', '16000')))
    acknowledgment_sound: str = Field(default_factory=lambda: os.getenv('ACKNOWLEDGMENT_SOUND', 'chime.wav'))
    thinking_sound: str = Field(default_factory=lambda: os.getenv('THINKING_SOUND', 'thinking.wav'))
    error_sound: str = Field(default_factory=lambda: os.getenv('ERROR_SOUND', 'error.wav'))
    enable_thinking_sound: bool = Field(default_factory=lambda: os.getenv('ENABLE_THINKING_SOUND', 'true').lower() == 'true')
    enable_error_sound: bool = Field(default_factory=lambda: os.getenv('ENABLE_ERROR_SOUND', 'true').lower() == 'true')
    
    # UniFi Protect (optional) - used for talkback (speaker) + mic capture via RTSP.
    # We use the *Protect Integration API* (local) via API key.
    # Example base: https://192.168.1.1/proxy/protect/integration/v1
    protect_base_url: str = Field(default_factory=lambda: os.getenv('PROTECT_BASE_URL', ''))
    protect_api_key: str = Field(default_factory=lambda: os.getenv('PROTECT_API_KEY', ''))
    protect_verify_ssl: bool = Field(default_factory=lambda: os.getenv('PROTECT_VERIFY_SSL', 'false').lower() == 'true')
    protect_camera_id: str = Field(default_factory=lambda: os.getenv('PROTECT_CAMERA_ID', ''))
    protect_rtsp_quality: str = Field(default_factory=lambda: os.getenv('PROTECT_RTSP_QUALITY', 'medium'))

    # If you already know the RTSP/RTSPS URL (or you want to use a non-Protect camera), set this.
    camera_rtsp_url: str = Field(default_factory=lambda: os.getenv('CAMERA_RTSP_URL', ''))

    # Runtime selection (set via the web UI)
    # This lets you keep infrastructure (hosts/keys) in env vars, while selecting cameras in the UI.
    runtime_config_path: str = Field(default_factory=lambda: os.getenv('RUNTIME_CONFIG_PATH', '/data/runtime.json'))
    frigate_camera: str = Field(default_factory=lambda: os.getenv('FRIGATE_CAMERA', ''))
    
    # Frigate configuration
    frigate_host: str = Field(default_factory=lambda: os.getenv('FRIGATE_HOST', 'frigate'))
    frigate_port: int = Field(default_factory=lambda: int(os.getenv('FRIGATE_PORT', '5000')))
    
    # MQTT configuration
    mqtt_host: str = Field(default_factory=lambda: os.getenv('MQTT_HOST', 'localhost'))
    mqtt_port: int = Field(default_factory=lambda: int(os.getenv('MQTT_PORT', '1883')))
    # Inbound topics
    # - mqtt_topic: Frigate events (default)
    # - mqtt_trigger_topic: manual triggers (Home Assistant, ESP32 doorbell, Node-RED, etc.)
    mqtt_topic: str = Field(default_factory=lambda: os.getenv('MQTT_TOPIC', 'frigate/events'))
    mqtt_trigger_topic: str = Field(default_factory=lambda: os.getenv('MQTT_TRIGGER_TOPIC', 'doorbell/trigger'))

    # Outbound topics
    # Publish the detected intent so you can handle actions however you want (HA automations, Node-RED, scripts, etc.)
    mqtt_intent_topic: str = Field(default_factory=lambda: os.getenv('MQTT_INTENT_TOPIC', 'doorbell/intent'))
    mqtt_status_topic: str = Field(default_factory=lambda: os.getenv('MQTT_STATUS_TOPIC', 'doorbell/status'))
    mqtt_publish_intent: bool = Field(default_factory=lambda: os.getenv('MQTT_PUBLISH_INTENT', 'true').lower() == 'true')
    mqtt_include_transcript: bool = Field(default_factory=lambda: os.getenv('MQTT_INCLUDE_TRANSCRIPT', 'true').lower() == 'true')
    
    # Behavior configuration
    response_timeout: int = Field(default_factory=lambda: int(os.getenv('RESPONSE_TIMEOUT', '5')))
    max_response_length: int = Field(default_factory=lambda: int(os.getenv('MAX_RESPONSE_LENGTH', '100')))
    
    # Paths
    sounds_dir: Path = Field(default=Path('/app/sounds'))
    cache_dir: Path = Field(default=Path('/app/cache'))
    config_dir: Path = Field(default=Path('/app/config'))
    
    # Debug settings
    debug: bool = Field(default_factory=lambda: os.getenv('DEBUG', 'false').lower() == 'true')
    log_level: str = Field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))

    # "Thought" logging (structured JSONL) for debugging sessions
    thought_log_enabled: bool = Field(default_factory=lambda: os.getenv('THOUGHT_LOG_ENABLED', 'false').lower() == 'true')
    thought_log_path: str = Field(default_factory=lambda: os.getenv('THOUGHT_LOG_PATH', '/data/thinking.log.jsonl'))
    thought_log_include_transcript: bool = Field(default_factory=lambda: os.getenv('THOUGHT_LOG_INCLUDE_TRANSCRIPT', 'false').lower() == 'true')
    thought_log_redact_pii: bool = Field(default_factory=lambda: os.getenv('THOUGHT_LOG_REDACT_PII', 'true').lower() == 'true')

    # Response templates (editable)
    templates_path: str = Field(default_factory=lambda: os.getenv('TEMPLATES_PATH', '/app/config/templates.yml'))

    # People logging (optional)
    people_log_enabled: bool = Field(default_factory=lambda: os.getenv('PEOPLE_LOG_ENABLED', 'false').lower() == 'true')
    people_log_dir: str = Field(default_factory=lambda: os.getenv('PEOPLE_LOG_DIR', '/data/people'))
    people_log_save_snapshot: bool = Field(default_factory=lambda: os.getenv('PEOPLE_LOG_SAVE_SNAPSHOT', 'true').lower() == 'true')
    people_log_save_thumbnail: bool = Field(default_factory=lambda: os.getenv('PEOPLE_LOG_SAVE_THUMBNAIL', 'false').lower() == 'true')
    frigate_api_key: str = Field(default_factory=lambda: os.getenv('FRIGATE_API_KEY', ''))

    # Frigate Face Library integration (optional)
    # Only register/train faces for allowlisted intents (default: solicitor).
    # Use with care: this is meant for deterrence (repeat solicitors), not general tracking.
    frigate_faces_enabled: bool = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_ENABLED', 'false').lower() == 'true')
    frigate_faces_intents: str = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_INTENTS', 'solicitor'))
    frigate_faces_min_confidence: float = Field(default_factory=lambda: float(os.getenv('FRIGATE_FACES_MIN_CONFIDENCE', '0.85')))
    frigate_faces_prefix: str = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_PREFIX', 'solicitor-'))
    frigate_faces_auto_train: bool = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_AUTO_TRAIN', 'true').lower() == 'true')
    frigate_faces_train_mode: str = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_TRAIN_MODE', 'classify'))
    frigate_faces_name_maxlen: int = Field(default_factory=lambda: int(os.getenv('FRIGATE_FACES_NAME_MAXLEN', '48')))
    frigate_faces_store_dir: str = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_STORE_DIR', '/data/faces'))
    frigate_faces_dry_run: bool = Field(default_factory=lambda: os.getenv('FRIGATE_FACES_DRY_RUN', 'false').lower() == 'true')


    
    class Config:
        arbitrary_types_allowed = True
    
    def validate_required_fields(self):
        """Validate that required fields are set"""
        errors = []

        runtime = self.runtime_config
        protect_cam = runtime.get('protect_camera_id') or self.protect_camera_id
        rtsp_url = runtime.get('camera_rtsp_url') or self.camera_rtsp_url
        
        # Protect is optional IF you provide CAMERA_RTSP_URL and you don't need talkback.
        # For the "full" G6 Entry experience (mic + speaker), set PROTECT_*.
        if not rtsp_url:
            # No manual RTSP URL, so we need Protect configured to discover RTSP.
            if not self.protect_base_url:
                errors.append("PROTECT_BASE_URL is required (or set CAMERA_RTSP_URL)")
            if not self.protect_api_key:
                errors.append("PROTECT_API_KEY is required (or set CAMERA_RTSP_URL)")
            if not protect_cam:
                errors.append("PROTECT_CAMERA_ID is required (or select a Protect camera in the UI)")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    @property
    def frigate_url(self) -> str:
        """Get full Frigate URL"""
        return f"http://{self.frigate_host}:{self.frigate_port}"

    @property
    def runtime_config(self) -> dict:
        """Load UI-managed runtime selections (camera IDs, etc.)."""
        return _load_runtime_config(self.runtime_config_path)

    @property
    def selected_frigate_camera(self) -> str:
        """Frigate camera name selected in UI (falls back to FRIGATE_CAMERA env var)."""
        return (self.runtime_config.get('frigate_camera') or self.frigate_camera or '').strip()

    @property
    def selected_protect_camera_id(self) -> str:
        """Protect camera ID selected in UI (falls back to PROTECT_CAMERA_ID env var)."""
        return (self.runtime_config.get('protect_camera_id') or self.protect_camera_id or '').strip()

    @property
    def selected_camera_rtsp_url(self) -> str:
        """RTSP URL selected in UI (falls back to CAMERA_RTSP_URL env var)."""
        return (self.runtime_config.get('camera_rtsp_url') or self.camera_rtsp_url or '').strip()

    @property
    def talkback_enabled(self) -> bool:
        return bool(self.protect_base_url and self.protect_api_key and self.selected_protect_camera_id)
    
    @property
    def acknowledgment_sound_path(self) -> Path:
        """Get full path to acknowledgment sound"""
        return self.sounds_dir / self.acknowledgment_sound
    
    @property
    def thinking_sound_path(self) -> Path:
        """Get full path to thinking sound"""
        return self.sounds_dir / self.thinking_sound
    
    @property
    def error_sound_path(self) -> Path:
        """Get full path to error sound"""
        return self.sounds_dir / self.error_sound
