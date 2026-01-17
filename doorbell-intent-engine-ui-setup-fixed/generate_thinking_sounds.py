#!/usr/bin/env python3
"""
Generate thinking/processing sounds for the doorbell system

This script creates various "thinking" sounds that can be played
while the system processes the visitor's speech.
"""

import numpy as np
import soundfile as sf
from pathlib import Path

SAMPLE_RATE = 16000
OUTPUT_DIR = Path("sounds")

def generate_soft_beep(duration=0.5, frequency=440):
    """Generate a soft, pleasant beep"""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Create tone with envelope
    tone = np.sin(2 * np.pi * frequency * t)
    
    # Apply fade in/out envelope
    envelope = np.ones_like(t)
    fade_samples = int(0.05 * SAMPLE_RATE)  # 50ms fade
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    audio = tone * envelope * 0.3  # Reduce volume
    return audio

def generate_three_tone_sequence():
    """Generate three rising tones (like a thinking indicator)"""
    tones = []
    frequencies = [440, 523, 659]  # A, C, E (major chord)
    
    for freq in frequencies:
        tone = generate_soft_beep(duration=0.3, frequency=freq)
        silence = np.zeros(int(0.1 * SAMPLE_RATE))  # 100ms gap
        tones.append(tone)
        tones.append(silence)
    
    return np.concatenate(tones)

def generate_gentle_hum():
    """Generate a gentle humming sound"""
    duration = 1.5
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Multiple frequencies for richness
    freq1 = 200
    freq2 = 300
    
    audio = (np.sin(2 * np.pi * freq1 * t) * 0.2 + 
             np.sin(2 * np.pi * freq2 * t) * 0.15)
    
    # Apply envelope
    envelope = np.ones_like(t)
    fade_samples = int(0.2 * SAMPLE_RATE)
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    return audio * envelope

def generate_quick_chirp():
    """Generate a quick, friendly chirp"""
    duration = 0.4
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Rising frequency chirp
    freq_start = 440
    freq_end = 880
    frequency = np.linspace(freq_start, freq_end, len(t))
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    
    audio = np.sin(phase) * 0.3
    
    # Quick fade
    envelope = np.ones_like(t)
    fade_samples = int(0.05 * SAMPLE_RATE)
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    return audio * envelope

def generate_subtle_click():
    """Generate a subtle mechanical 'processing' click"""
    duration = 0.2
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Quick burst of noise with tone
    noise = np.random.randn(len(t)) * 0.1
    tone = np.sin(2 * np.pi * 800 * t) * 0.2
    
    # Very quick envelope
    envelope = np.exp(-t * 20)
    
    return (noise + tone) * envelope

def generate_tts_thinking_phrase():
    """
    Note: This would use TTS to say something like:
    - "One moment..."
    - "Let me think..."
    - "Just a second..."
    
    For now, returns None to indicate TTS should be used
    """
    return None

def main():
    """Generate all thinking sounds"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("Generating thinking sounds...")
    
    # Generate various options
    sounds = {
        "thinking.wav": generate_three_tone_sequence(),
        "thinking_hum.wav": generate_gentle_hum(),
        "thinking_chirp.wav": generate_quick_chirp(),
        "thinking_beep.wav": generate_soft_beep(duration=0.8),
        "thinking_click.wav": generate_subtle_click(),
    }
    
    for filename, audio in sounds.items():
        output_path = OUTPUT_DIR / filename
        sf.write(output_path, audio, SAMPLE_RATE)
        print(f"✓ Generated: {output_path}")
    
    print("\nGenerated sounds:")
    print("  - thinking.wav (default) - Three rising tones")
    print("  - thinking_hum.wav - Gentle hum")
    print("  - thinking_chirp.wav - Quick chirp")
    print("  - thinking_beep.wav - Soft beep")
    print("  - thinking_click.wav - Subtle click")
    print("\nTo use a different sound, update THINKING_SOUND in .env")
    print("Or record your own and place it in the sounds/ directory!")

if __name__ == "__main__":
    main()
