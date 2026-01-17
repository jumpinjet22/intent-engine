"""TTS (Text-to-Speech) handler supporting multiple engines"""

import logging
import asyncio
from pathlib import Path
from typing import Optional
import numpy as np

from config import Config

logger = logging.getLogger(__name__)


class TTSHandler:
    """Handle TTS operations with support for multiple engines"""
    
    def __init__(self, config: Config):
        self.config = config
        self.tts_engine = None
        self.engine_type = config.tts_engine.lower()
        
    async def initialize(self):
        """Initialize the TTS engine"""
        logger.info(f"Initializing TTS engine: {self.engine_type}")
        
        if self.engine_type == 'xtts':
            await self._init_xtts()
        elif self.engine_type == 'piper':
            await self._init_piper()
        elif self.engine_type == 'kokoro':
            await self._init_kokoro()
        else:
            raise ValueError(f"Unsupported TTS engine: {self.engine_type}")
        
        logger.info("TTS engine initialized")
    
    async def _init_xtts(self):
        """Initialize XTTS (Coqui TTS)"""
        try:
            from TTS.api import TTS
            
            model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
            logger.info(f"Loading XTTS model: {model_name}")
            
            self.tts_engine = TTS(model_name).to("cuda")
            
            # Set voice sample if provided
            if self.config.enable_voice_cloning and self.config.tts_voice_sample:
                logger.info(f"Voice cloning enabled with sample: {self.config.tts_voice_sample}")
            
        except Exception as e:
            logger.error(f"Error initializing XTTS: {e}")
            raise
    
    async def _init_piper(self):
        """Initialize Piper TTS"""
        try:
            from piper import PiperVoice
            
            # Download a voice model if not present
            model_path = self.config.cache_dir / "piper_model"
            model_path.mkdir(parents=True, exist_ok=True)
            
            # Use a default voice (you can customize this)
            voice_file = model_path / "en_US-lessac-medium.onnx"
            
            if not voice_file.exists():
                logger.info("Downloading Piper voice model...")
                # Download logic here - for now, assume it exists
                logger.warning("Piper model not found - please download manually")
            
            self.tts_engine = PiperVoice.load(str(voice_file))
            
        except Exception as e:
            logger.error(f"Error initializing Piper: {e}")
            raise
    
    async def _init_kokoro(self):
        """Initialize Kokoro TTS"""
        try:
            # Kokoro initialization
            # This is a placeholder - actual implementation depends on kokoro-onnx
            logger.warning("Kokoro TTS not fully implemented yet")
            raise NotImplementedError("Kokoro TTS support coming soon")
            
        except Exception as e:
            logger.error(f"Error initializing Kokoro: {e}")
            raise
    
    async def synthesize(self, text: str) -> np.ndarray:
        """
        Synthesize speech from text
        
        Args:
            text: Text to synthesize
            
        Returns:
            Audio data as numpy array (float32, mono)
        """
        if self.engine_type == 'xtts':
            return await self._synthesize_xtts(text)
        elif self.engine_type == 'piper':
            return await self._synthesize_piper(text)
        elif self.engine_type == 'kokoro':
            return await self._synthesize_kokoro(text)
        else:
            raise ValueError(f"Unknown TTS engine: {self.engine_type}")
    
    async def _synthesize_xtts(self, text: str) -> np.ndarray:
        """Synthesize with XTTS"""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def _generate():
                if self.config.enable_voice_cloning and self.config.tts_voice_sample:
                    # Voice cloning
                    wav = self.tts_engine.tts(
                        text=text,
                        speaker_wav=self.config.tts_voice_sample,
                        language="en"
                    )
                else:
                    # Default voice
                    wav = self.tts_engine.tts(text=text, language="en")
                
                return np.array(wav, dtype=np.float32)
            
            audio = await loop.run_in_executor(None, _generate)
            return audio
            
        except Exception as e:
            logger.error(f"Error synthesizing with XTTS: {e}")
            raise
    
    async def _synthesize_piper(self, text: str) -> np.ndarray:
        """Synthesize with Piper"""
        try:
            loop = asyncio.get_event_loop()
            
            def _generate():
                audio_stream = self.tts_engine.synthesize_stream_raw(text)
                audio_data = b''.join(audio_stream)
                
                # Convert bytes to numpy array
                audio = np.frombuffer(audio_data, dtype=np.int16)
                # Convert to float32 and normalize
                audio = audio.astype(np.float32) / 32768.0
                return audio
            
            audio = await loop.run_in_executor(None, _generate)
            return audio
            
        except Exception as e:
            logger.error(f"Error synthesizing with Piper: {e}")
            raise
    
    async def _synthesize_kokoro(self, text: str) -> np.ndarray:
        """Synthesize with Kokoro"""
        # Placeholder
        raise NotImplementedError("Kokoro synthesis not implemented")
    
    def get_sample_rate(self) -> int:
        """Get the native sample rate of the TTS engine"""
        if self.engine_type == 'xtts':
            return 24000  # XTTS outputs at 24kHz
        elif self.engine_type == 'piper':
            return 22050  # Piper default
        elif self.engine_type == 'kokoro':
            return 24000  # Kokoro default
        return 22050  # Default fallback
    
    async def cleanup(self):
        """Cleanup TTS resources"""
        logger.info("Cleaning up TTS handler")
        self.tts_engine = None
