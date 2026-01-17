"""Core intent engine implementation"""

import asyncio
import logging
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, List
import numpy as np
from pathlib import Path

import ollama
from faster_whisper import WhisperModel
import requests
import ffmpeg

from config import Config
from tts_handler import TTSHandler
from protect_handler import ProtectIntegrationHandler
from thought_logger import ThoughtLogger
from template_manager import TemplateManager
from people_logger import PeopleLogger, PeopleLoggerConfig
from frigate_faces import FrigateFaceClient, FrigateFaceConfig

logger = logging.getLogger(__name__)


class DoorbellIntentEngine:
    """Main intent engine for doorbell interactions"""
    
    def __init__(self, config: Config):
        self.config = config
        self.whisper = None
        self.tts_handler = None
        self.protect_handler = None
        self.ollama_client = None
        self.mqtt_client = None

        # Editable response templates
        self.templates = TemplateManager(self.config.templates_path)

        # Optional people/event logging (snapshots + metadata)
        self.people_logger = PeopleLogger(
            PeopleLoggerConfig(
                enabled=bool(self.config.people_log_enabled),
                log_dir=Path(self.config.people_log_dir),
                frigate_url=str(self.config.frigate_url),
                frigate_api_key=str(self.config.frigate_api_key or ""),
                save_snapshot=bool(self.config.people_log_save_snapshot),
                save_thumbnail=bool(self.config.people_log_save_thumbnail),
            )
        )

        # Structured "thought" logging (JSONL) for debugging
        self.thought_logger = ThoughtLogger(
            enabled=bool(self.config.thought_log_enabled),
            path=str(self.config.thought_log_path),
            include_transcript=bool(self.config.thought_log_include_transcript),
            redact_pii=bool(self.config.thought_log_redact_pii),
        )

        # Optional Frigate Face Library integration (repeat solicitor deterrence)
        self.frigate_faces = FrigateFaceClient(
            FrigateFaceConfig(
                enabled=bool(self.config.frigate_faces_enabled),
                frigate_url=str(self.config.frigate_url),
                api_key=str(self.config.frigate_api_key or ''),
                dry_run=bool(self.config.frigate_faces_dry_run),
                store_dir=Path(str(self.config.frigate_faces_store_dir)),
                allowed_intents=tuple([s.strip().lower() for s in str(self.config.frigate_faces_intents).split(',') if s.strip()]),
                min_confidence=float(self.config.frigate_faces_min_confidence),
                prefix=str(self.config.frigate_faces_prefix),
                auto_train=bool(self.config.frigate_faces_auto_train),
                train_mode=str(self.config.frigate_faces_train_mode),
                name_maxlen=int(self.config.frigate_faces_name_maxlen),
            )
        )

    def _new_session_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def _tlog(self, event: str, session_id: str, **fields):
        """Best-effort thought logging (never crash interaction)."""
        try:
            self.thought_logger.log(event, session_id, **fields)
        except Exception as e:
            logger.debug(f"Thought logging failed: {e}")

    def set_mqtt_client(self, mqtt_client):
        """Allow the engine to publish intent/status over MQTT."""
        self.mqtt_client = mqtt_client

    def _mqtt_publish(self, topic: str, payload: Dict):
        """Best-effort MQTT publish (never crash the interaction)."""
        if not self.mqtt_client or not topic:
            return
        try:
            self.mqtt_client.publish(topic, json.dumps(payload), qos=0, retain=False)
        except Exception as e:
            logger.warning(f"Failed to publish MQTT message to {topic}: {e}")
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing components...")
        
        # Validate configuration
        self.config.validate_required_fields()
        
        # Initialize Whisper
        logger.info(f"Loading Whisper model: {self.config.whisper_model}")
        self.whisper = WhisperModel(
            self.config.whisper_model,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type
        )
        
        # Initialize TTS handler
        logger.info(f"Initializing TTS handler: {self.config.tts_engine}")
        self.tts_handler = TTSHandler(self.config)
        await self.tts_handler.initialize()
        
        # Initialize Protect handler (optional). If not configured, we can still run
        # classification + MQTT publishing, but audio I/O will be limited.
        if self.config.talkback_enabled or self.config.camera_rtsp_url:
            logger.info("Initializing Protect Integration API handler")
            self.protect_handler = ProtectIntegrationHandler(self.config)
        else:
            logger.warning("Protect not configured and no CAMERA_RTSP_URL provided; audio capture/talkback disabled")
        
        # Test Ollama connection
        logger.info(f"Connecting to Ollama at {self.config.ollama_host}")
        await self.test_ollama_connection()
        
        logger.info("Initialization complete")
    
    async def test_ollama_connection(self):
        """Test connection to Ollama and ensure model is available"""
        try:
            # Check if model is available
            response = ollama.list()
            models = [m['name'] for m in response.get('models', [])]
            
            if self.config.llm_model not in models:
                logger.warning(f"Model {self.config.llm_model} not found. Pulling...")
                ollama.pull(self.config.llm_model)
                logger.info(f"Model {self.config.llm_model} pulled successfully")
            else:
                logger.info(f"Model {self.config.llm_model} is available")
                
        except Exception as e:
            logger.error(f"Error connecting to Ollama: {e}")
            raise
    
    async def handle_doorbell_event(self, frigate_event: Dict):
        """
        Main handler for doorbell events
        
        Args:
            frigate_event: Event data from Frigate
        """
        try:
            session_id = self._new_session_id()
            t_start = time.perf_counter()

            # Extract context from Frigate event
            context = self.extract_frigate_context(frigate_event)
            logger.info(f"Event context: {context}")

            self._tlog(
                "session_started",
                session_id,
                source="frigate",
                camera=context.get("camera", ""),
                time_of_day=context.get("time_of_day"),
                context=context,
            )

            # Notify status
            self._mqtt_publish(self.config.mqtt_status_topic, {
                "event": "doorbell_triggered",
                "source": "frigate",
                "timestamp": datetime.now().isoformat(),
                "context": context,
            })
            
            # Play immediate acknowledgment
            self._tlog("acknowledgment", session_id)
            await self.play_acknowledgment()
            
            # Wait for and capture visitor audio
            logger.info("Waiting for visitor to speak...")
            t_cap0 = time.perf_counter()
            visitor_audio = await self.capture_visitor_audio()
            t_cap_ms = int((time.perf_counter() - t_cap0) * 1000)

            self._tlog(
                "audio_captured",
                session_id,
                ok=visitor_audio is not None,
                capture_ms=t_cap_ms,
            )
            
            if visitor_audio is None:
                logger.warning("No audio captured from visitor")
                # Play a default response
                await self.play_default_response()
                return
            
            # Transcribe audio
            logger.info("Transcribing audio...")
            t_asr0 = time.perf_counter()
            transcript = await self.transcribe_audio(visitor_audio)
            t_asr_ms = int((time.perf_counter() - t_asr0) * 1000)
            logger.info(f"Transcript: {transcript}")

            self._tlog(
                "asr_result",
                session_id,
                transcript=transcript,
                asr_ms=t_asr_ms,
            )
            
            if not transcript or len(transcript.strip()) < 3:
                logger.warning("Transcript too short or empty")
                await self.play_default_response()
                return

            # Detect intent + publish it so automations can do whatever they want
            t_llm0 = time.perf_counter()
            intent_result = await self.classify_intent(context, transcript)
            t_llm_ms = int((time.perf_counter() - t_llm0) * 1000)

            self._tlog(
                "llm_classification",
                session_id,
                intent=intent_result.get("intent", "unknown") if isinstance(intent_result, dict) else "unknown",
                confidence=float(intent_result.get("confidence", 0.0)) if isinstance(intent_result, dict) else 0.0,
                suggested_actions=intent_result.get("suggested_actions", []) if isinstance(intent_result, dict) else [],
                llm_ms=t_llm_ms,
            )
            # Derive handoff + select a spoken response from templates
            human_handoff = self._derive_human_handoff(intent_result, context)
            tr = self.templates.render(
                intent=(intent_result or {}).get("intent", "unknown"),
                context=context,
                intent_result=intent_result or {},
                requires_human=bool(human_handoff.get("required", False)),
            )

            # Publish intent (includes requires_human + the response chosen)
            await self.publish_intent(
                intent_result,
                context,
                transcript,
                source="frigate",
                response_text=tr.text,
                template_id=tr.template_id,
                human_handoff=human_handoff,
            )
            self._tlog("response_selected", session_id, response_text=tr.text, mode="template", template_id=tr.template_id)
            await self.speak_text(tr.text)

            # Optional: log artifacts for later review/training
            try:
                self.people_logger.log_event(
                    session_id=session_id,
                    event_id=context.get("event_id"),
                    camera=context.get("camera", ""),
                    intent=(intent_result or {}).get("intent", "unknown"),
                    transcript=transcript,
                    intent_payload={
                        "intent": (intent_result or {}).get("intent", "unknown"),
                        "confidence": float((intent_result or {}).get("confidence", 0.0)),
                        "entities": (intent_result or {}).get("entities", {}),
                        "suggested_actions": (intent_result or {}).get("suggested_actions", []),
                        "human_handoff": human_handoff,
                    },
                    context=context,
                )
            except Exception:
                pass

            # Optional: register/train solicitor faces in Frigate (opt-in)
            try:
                asyncio.create_task(self._maybe_register_faces(session_id, intent_result, context, transcript))
            except Exception:
                pass

            total_ms = int((time.perf_counter() - t_start) * 1000)
            self._tlog(
                "session_finished",
                session_id,
                total_ms=total_ms,
                capture_ms=t_cap_ms,
                asr_ms=t_asr_ms,
                llm_ms=t_llm_ms,
            )
            
        except Exception as e:
            logger.error(f"Error handling doorbell event: {e}", exc_info=True)
            try:
                self._tlog("session_error", session_id, error=str(e))
            except Exception:
                pass
            # Try to play an error response
            try:
                await self.speak_text("I'm sorry, I'm having trouble responding right now.")
            except:
                pass

    async def handle_trigger_event(self, trigger: Dict):
        """Handle a manual trigger (e.g., HA/ESP32 publishes to doorbell/trigger)."""
        try:
            session_id = self._new_session_id()
            t_start = time.perf_counter()
            context = self.extract_trigger_context(trigger)
            logger.info(f"Trigger context: {context}")

            self._tlog(
                "session_started",
                session_id,
                source=str(trigger.get("source", "trigger")),
                camera=str(context.get("camera_id", "")),
                time_of_day=context.get("time_of_day"),
                context=context,
            )

            self._mqtt_publish(self.config.mqtt_status_topic, {
                "event": "doorbell_triggered",
                "source": trigger.get("source", "trigger"),
                "timestamp": datetime.now().isoformat(),
                "context": context,
            })

            self._tlog("acknowledgment", session_id)
            await self.play_acknowledgment()

            t_cap0 = time.perf_counter()
            visitor_audio = await self.capture_visitor_audio()
            t_cap_ms = int((time.perf_counter() - t_cap0) * 1000)
            self._tlog("audio_captured", session_id, ok=visitor_audio is not None, capture_ms=t_cap_ms)
            if visitor_audio is None:
                await self.play_default_response()
                return

            t_asr0 = time.perf_counter()
            transcript = await self.transcribe_audio(visitor_audio)
            t_asr_ms = int((time.perf_counter() - t_asr0) * 1000)
            logger.info(f"Transcript: {transcript}")
            self._tlog("asr_result", session_id, transcript=transcript, asr_ms=t_asr_ms)
            if not transcript or len(transcript.strip()) < 3:
                await self.play_default_response()
                return

            t_llm0 = time.perf_counter()
            intent_result = await self.classify_intent(context, transcript)
            t_llm_ms = int((time.perf_counter() - t_llm0) * 1000)
            self._tlog(
                "llm_classification",
                session_id,
                intent=intent_result.get("intent", "unknown") if isinstance(intent_result, dict) else "unknown",
                confidence=float(intent_result.get("confidence", 0.0)) if isinstance(intent_result, dict) else 0.0,
                suggested_actions=intent_result.get("suggested_actions", []) if isinstance(intent_result, dict) else [],
                llm_ms=t_llm_ms,
            )
            human_handoff = self._derive_human_handoff(intent_result, context)
            tr = self.templates.render(
                intent=(intent_result or {}).get("intent", "unknown"),
                context=context,
                intent_result=intent_result or {},
                requires_human=bool(human_handoff.get("required", False)),
            )

            await self.publish_intent(
                intent_result,
                context,
                transcript,
                source=trigger.get("source", "trigger"),
                response_text=tr.text,
                template_id=tr.template_id,
                human_handoff=human_handoff,
            )
            self._tlog("response_selected", session_id, response_text=tr.text, mode="template", template_id=tr.template_id)
            await self.speak_text(tr.text)

            total_ms = int((time.perf_counter() - t_start) * 1000)
            self._tlog("session_finished", session_id, total_ms=total_ms, capture_ms=t_cap_ms, asr_ms=t_asr_ms, llm_ms=t_llm_ms)

        except Exception as e:
            logger.error(f"Error handling trigger event: {e}", exc_info=True)
            try:
                self._tlog("session_error", session_id, error=str(e))
            except Exception:
                pass
            try:
                await self.speak_text("I'm sorry, I'm having trouble responding right now.")
            except:
                pass
    
    def extract_frigate_context(self, event: Dict) -> Dict:
        """Extract relevant context from Frigate event"""
        after = event.get('after', {})
        
        context = {
            'timestamp': datetime.now().isoformat(),
            'event_id': after.get('id') or (event.get('after', {}) or {}).get('id') or (event.get('before', {}) or {}).get('id'),
            'camera': after.get('camera', ''),
            'label': after.get('label', ''),
            'zones': after.get('current_zones', []),
            'has_person': after.get('label') == 'person',
            'has_package': False,  # Will be updated based on sub-labels
            'has_vehicle': False,
            'stationary': after.get('stationary', False),
            'time_of_day': self.get_time_of_day(),
        }
        
        # Check sub-labels for packages, vehicles, etc.
        sub_labels = after.get('sub_label', [])
        # Frigate uses sub_label as a string for many object types; some setups may emit lists.
        if isinstance(sub_labels, str):
            sub_labels = [sub_labels]
        if isinstance(sub_labels, list):
            sub_l = {str(s).lower() for s in sub_labels}
            context['has_package'] = any(x in sub_l for x in {'package', 'box'})
            context['has_vehicle'] = any(x in sub_l for x in {'car', 'truck', 'van'})

        # If sub_label looks like a known person/face name (not package/vehicle), capture it
        recognized = None
        if isinstance(after.get('sub_label'), str):
            s = after.get('sub_label').strip()
            if s and s.lower() not in {'package', 'box', 'car', 'truck', 'van'}:
                recognized = s
        context['recognized_person'] = recognized

        # Repeat offender hint: if Frigate already recognizes a solicitor-* identity, we can be firmer
        rp = (recognized or '').lower()
        context['repeat_offender'] = bool(rp and rp.startswith(str(self.config.frigate_faces_prefix).lower()))
        
        return context

    def extract_trigger_context(self, trigger: Dict) -> Dict:
        """Extract context from a manual trigger payload."""
        context_in = trigger.get("context") or {}
        return {
            "timestamp": datetime.now().isoformat(),
            "camera_id": trigger.get("camera_id") or self.config.camera_id,
            "camera_name": trigger.get("camera_name", ""),
            "source": trigger.get("source", "trigger"),
            "trigger_type": context_in.get("trigger_type", "doorbell_press"),
            "location": context_in.get("location", "front_door"),
            "custom_prompt": context_in.get("custom_prompt", "Someone pressed the doorbell"),
            "time_of_day": context_in.get("time_of_day") or self.get_time_of_day(),
            # Optional hints
            "has_package": bool(context_in.get("has_package", False)),
            "has_vehicle": bool(context_in.get("has_vehicle", False)),
            "expected_guest": context_in.get("expected_guest"),
        }

    async def classify_intent(self, context: Dict, transcript: str) -> Dict:
        """Return a structured intent object from the visitor's transcript."""
        prompt = self.build_intent_prompt(context, transcript)
        try:
            res = ollama.generate(
                model=self.config.llm_model,
                prompt=prompt,
                stream=False,
                options={
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "max_tokens": 300,
                },
            )
            text = (res.get("response") or "").strip()

            # Strip common code-fence wrappers
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text.rsplit("```", 1)[0]
                text = text.strip()

            data = json.loads(text)
            return data if isinstance(data, dict) else {"intent": "unknown", "confidence": 0.0}

        except Exception as e:
            logger.warning(f"Intent classification failed, falling back to unknown: {e}")
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": {},
                "suggested_actions": [],
            }

    def build_intent_prompt(self, context: Dict, transcript: str) -> str:
        """Prompt the LLM to produce a strict JSON intent packet."""

        # Minimal context string
        ctx_bits = []
        for k in ["time_of_day", "has_package", "has_vehicle", "trigger_type", "location", "expected_guest"]:
            if k in context and context.get(k) not in (None, "", []):
                ctx_bits.append(f"{k}={context.get(k)}")
        ctx = ", ".join(ctx_bits) if ctx_bits else "(none)"

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

Context: {ctx}
Visitor said: "{transcript}"

Return JSON with EXACT keys:
{{
  "intent": "one of the allowed intents",
  "confidence": 0.0,
  "entities": {{"name": "", "company": "", "tracking": "", "appointment_time": ""}},
  "suggested_actions": ["short action strings"]
}}

Rules:
- confidence is 0.0 to 1.0
 - suggested_actions can include: signature_required, notify_owner, unlock_door, etc.
"""

    async def publish_intent(
        self,
        intent_result: Dict,
        context: Dict,
        transcript: str,
        source: str = "unknown",
        *,
        response_text: str = "",
        template_id: str = "",
        human_handoff: Optional[Dict] = None,
    ):
        """Publish intent over MQTT so HA/Node-RED can decide what to do."""
        if not self.config.mqtt_publish_intent:
            return

        human_handoff = human_handoff or self._derive_human_handoff(intent_result, context)

        payload = {
            "schema_version": 1,
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "intent": intent_result.get("intent", "unknown") if isinstance(intent_result, dict) else "unknown",
            "confidence": float(intent_result.get("confidence", 0.0)) if isinstance(intent_result, dict) else 0.0,
            "entities": intent_result.get("entities", {}) if isinstance(intent_result, dict) else {},
            "suggested_actions": intent_result.get("suggested_actions", []) if isinstance(intent_result, dict) else [],
            "response_text": response_text or "",
            "template_id": template_id or "",
            "requires_human": bool(human_handoff.get("required", False)),
            "priority": human_handoff.get("priority", "low"),
            "handoff_reason": human_handoff.get("reason"),
            "human_handoff": human_handoff,
            "notify": human_handoff.get("notify", {"owner": False, "channels": []}),
            "context": context,
        }
        if self.config.mqtt_include_transcript:
            payload["transcript"] = transcript

        self._mqtt_publish(self.config.mqtt_intent_topic, payload)


    async def _maybe_register_faces(self, session_id: str, intent_result: Dict, context: Dict, transcript: str) -> None:
        """Opt-in: register/train a face in Frigate's face library.

        Policy:
        - Only run if FRIGATE_FACES_ENABLED=true
        - Only for allowlisted intents (default: solicitor)
        - Only if confidence >= FRIGATE_FACES_MIN_CONFIDENCE
        - Only if we have an event_id and a reasonable label to attach

        This runs best-effort and never blocks or breaks the main interaction.
        """
        try:
            if not getattr(self.config, "frigate_faces_enabled", False):
                return

            intent = (intent_result or {}).get("intent", "unknown") if isinstance(intent_result, dict) else "unknown"
            allowed = {s.strip().lower() for s in str(getattr(self.config, "frigate_faces_intents", "")).split(',') if s.strip()}
            if allowed and intent.lower() not in allowed:
                return

            # Don't auto-register if Frigate already recognized them as one of our deterrence labels
            if bool((context or {}).get("repeat_offender")):
                return

            conf = float((intent_result or {}).get("confidence", 0.0)) if isinstance(intent_result, dict) else 0.0
            if conf < float(getattr(self.config, "frigate_faces_min_confidence", 0.85)):
                return

            event_id = (context or {}).get("event_id")
            if not event_id:
                return

            entities = (intent_result or {}).get("entities") or {}
            raw_label = (entities.get("company") or "").strip()
            if len(raw_label) < 3:
                # As a fallback, try to extract a short keyword from the transcript
                raw_label = "".join([c for c in transcript.strip()[:32] if c.isalnum() or c in " -_"]).strip()

            if len(raw_label) < 3:
                # Too weak / too generic -> skip. (Avoid labeling random visitors as "unknown".)
                return

            face_name = await asyncio.to_thread(
                self.frigate_faces.register_from_event,
                event_id=str(event_id),
                label=raw_label,
            )

            if face_name:
                self._tlog("face_registered", session_id, event_id=event_id, face_name=face_name, label=raw_label)
                self._mqtt_publish(self.config.mqtt_status_topic, {
                    "event": "face_registered",
                    "timestamp": datetime.now().isoformat(),
                    "event_id": event_id,
                    "face_name": face_name,
                    "label": raw_label,
                    "intent": intent,
                })
            else:
                self._tlog("face_register_failed", session_id, event_id=event_id, label=raw_label, intent=intent)
        except Exception as e:
            try:
                self._tlog("face_register_error", session_id, error=str(e))
            except Exception:
                pass
            return

    def _derive_human_handoff(self, intent_result: Dict, context: Dict) -> Dict:
        """Derive whether a human should be involved and how urgent it is.

        Design goals:
        - Keep the MQTT topic stable (doorbell/intent)
        - Encode routing/urgency in payload fields (requires_human, priority, handoff_reason)
        - Let HA/Node-RED decide the actual actions
        """

        intent = (intent_result or {}).get("intent", "unknown") if isinstance(intent_result, dict) else "unknown"
        suggested = (intent_result or {}).get("suggested_actions", []) if isinstance(intent_result, dict) else []
        suggested_l = {str(s).lower() for s in (suggested or [])}

        time_of_day = (context or {}).get("time_of_day")

        required = False
        reason = None
        priority = "low"  # low | medium | high
        notify_owner = False
        notify_channels = []

        # Explicit signals from the model (preferred)
        if any(x in suggested_l for x in {"signature_required", "human_required", "needs_human", "handoff"}):
            required = True
            priority = "medium"
            if "signature_required" in suggested_l:
                reason = "signature_required"
            else:
                reason = "model_requested_handoff"
            notify_owner = True
            notify_channels = ["mobile_push"]

        # Hard safety cases
        if intent == "emergency":
            required = True
            priority = "high"
            reason = reason or "emergency"
            notify_owner = True
            notify_channels = ["mobile_push", "alarm"]

        # Suspicious unknowns at night
        if intent == "unknown" and time_of_day == "night":
            required = True
            priority = "high"
            reason = reason or "unknown_at_night"
            notify_owner = True
            notify_channels = ["mobile_push"]

        # Solicitors: usually not a "human required" scenario, but you may want a heads-up.
        # If Frigate already recognizes them as a repeat offender, escalate the priority a bit.
        if intent == "solicitor" and bool((context or {}).get("repeat_offender")):
            priority = "medium"
            reason = reason or "repeat_solicitor"
            notify_owner = True
            notify_channels = ["mobile_push"]

        # Keep it non-blocking by default.
        if intent == "solicitor" and not required:
            notify_owner = True
            notify_channels = ["mobile_push"]

        # Deliveries: not human required unless explicitly signaled.
        if intent == "delivery" and "notify_owner" in suggested_l:
            notify_owner = True
            notify_channels = ["mobile_push"]

        # If the engine is unsure, nudge toward notification rather than silence.
        confidence = float((intent_result or {}).get("confidence", 0.0)) if isinstance(intent_result, dict) else 0.0
        if confidence < 0.35 and not notify_owner:
            notify_owner = True
            notify_channels = ["mobile_push"]
            if not reason:
                reason = "low_confidence"

        return {
            "required": required,
            "reason": reason,
            "priority": priority,
            # Optional: a countdown before escalating (HA/Node-RED can implement timers)
            "deadline_seconds": 180 if required else None,
            "fallback": "notify_only" if required else None,
            "notify": {
                "owner": bool(notify_owner),
                "channels": notify_channels,
            },
        }
    
    def get_time_of_day(self) -> str:
        """Get time of day classification"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 21:
            return 'evening'
        else:
            return 'night'
    
    async def play_acknowledgment(self):
        """Play immediate acknowledgment sound"""
        try:
            sound_path = self.config.acknowledgment_sound_path
            if sound_path.exists():
                if self.protect_handler:
                    await self.protect_handler.play_audio_file(sound_path)
                else:
                    await self.speak_text("Hello!")
            else:
                logger.warning(f"Acknowledgment sound not found: {sound_path}")
                # Generate a quick "Hello" with TTS
                await self.speak_text("Hello!")
        except Exception as e:
            logger.error(f"Error playing acknowledgment: {e}")
    
    async def capture_visitor_audio(self, duration: int = None) -> Optional[np.ndarray]:
        """
        Capture audio from the G6 Entry microphone
        
        Args:
            duration: Duration in seconds (default from config)
            
        Returns:
            Audio data as numpy array or None
        """
        if duration is None:
            duration = self.config.response_timeout
        
        try:
            if not self.protect_handler:
                logger.warning("No audio capture backend configured")
                return None
            audio_data = await self.protect_handler.capture_audio(duration)
            return audio_data
        except Exception as e:
            logger.error(f"Error capturing visitor audio: {e}")
            return None
    
    async def transcribe_audio(self, audio_data: np.ndarray) -> str:
        """
        Transcribe audio using Whisper
        
        Args:
            audio_data: Audio as numpy array
            
        Returns:
            Transcribed text
        """
        try:
            # Whisper expects float32 audio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32) / 32768.0
            
            segments, info = self.whisper.transcribe(
                audio_data,
                language="en",
                beam_size=5,
                vad_filter=True  # Filter out non-speech
            )
            
            transcript = " ".join([segment.text.strip() for segment in segments])
            return transcript.strip()
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return ""
    
    async def generate_and_speak_response(self, context: Dict, transcript: str):
        """
        Generate response with LLM and stream to TTS
        
        Args:
            context: Context from Frigate
            transcript: What the visitor said
        """
        try:
            # Build prompt
            prompt = self.build_prompt(context, transcript)
            
            # Stream LLM response and speak
            await self.stream_llm_to_speech(prompt)
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def build_prompt(self, context: Dict, transcript: str) -> str:
        """Build LLM prompt with context"""
        
        time_greeting = {
            'morning': 'Good morning',
            'afternoon': 'Good afternoon',
            'evening': 'Good evening',
            'night': 'Hello'
        }.get(context['time_of_day'], 'Hello')
        
        context_desc = []
        if context['has_package']:
            context_desc.append("The person appears to have a package")
        if context['has_vehicle']:
            context_desc.append("There's a vehicle nearby (possibly delivery or rideshare)")
        if context['stationary']:
            context_desc.append("The person has been waiting at the door")
        
        context_str = ". ".join(context_desc) if context_desc else "Someone is at the door"
        
        prompt = f"""You are a friendly, helpful doorbell assistant. Respond naturally and briefly.

Time of day: {context['time_of_day']}
Context: {context_str}
Visitor said: "{transcript}"

Provide a brief, natural response (1-2 sentences maximum). Be helpful and friendly.
Use appropriate greeting for time of day ({time_greeting}).
Keep response under {self.config.max_response_length} words.

Response:"""
        
        return prompt
    
    async def stream_llm_to_speech(self, prompt: str):
        """Stream LLM output directly to TTS and speaker"""
        
        sentence_buffer = ""
        
        try:
            response = ollama.generate(
                model=self.config.llm_model,
                prompt=prompt,
                stream=True,
                options={
                    'temperature': 0.7,
                    'top_p': 0.9,
                    'max_tokens': self.config.max_response_length,
                }
            )
            
            for chunk in response:
                token = chunk['response']
                sentence_buffer += token
                
                # When we hit sentence boundary, synthesize and play
                if token in '.!?\n' and len(sentence_buffer.strip()) > 10:
                    sentence = sentence_buffer.strip()
                    logger.info(f"Speaking: {sentence}")
                    
                    await self.speak_text(sentence)
                    sentence_buffer = ""
            
            # Handle any remaining text
            if sentence_buffer.strip():
                logger.info(f"Speaking final: {sentence_buffer.strip()}")
                await self.speak_text(sentence_buffer.strip())
                
        except Exception as e:
            logger.error(f"Error in LLM streaming: {e}")
            raise
    
    async def speak_text(self, text: str):
        """Synthesize and play text through doorbell speaker"""
        try:
            # Generate audio with TTS
            audio_data = await self.tts_handler.synthesize(text)
            
            # Stream to camera
            if self.protect_handler:
                await self.protect_handler.stream_audio(audio_data)
            
        except Exception as e:
            logger.error(f"Error speaking text: {e}")
            raise
    
    async def play_default_response(self):
        """Play a default response when we can't understand the visitor"""
        responses = [
            "I'm sorry, I didn't catch that. Please try again.",
            "Could you please repeat that?",
            "I didn't hear you clearly. Please speak a bit louder."
        ]
        
        import random
        response = random.choice(responses)
        await self.speak_text(response)
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        if self.tts_handler:
            await self.tts_handler.cleanup()
        
        if self.protect_handler:
            await self.protect_handler.cleanup()
        
        logger.info("Cleanup complete")
