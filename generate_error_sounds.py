#!/usr/bin/env python3
"""
Generate error/failure sounds for the doorbell system

Creates various error indication sounds for when processing fails
"""

import numpy as np
import soundfile as sf
from pathlib import Path

SAMPLE_RATE = 16000
OUTPUT_DIR = Path("sounds")

def generate_descending_tones():
    """Generate descending tones (indicates failure/error)"""
    tones = []
    frequencies = [659, 523, 440]  # E, C, A (descending)
    
    for freq in frequencies:
        duration = 0.25
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
        
        # Create tone with envelope
        tone = np.sin(2 * np.pi * freq * t)
        
        # Apply fade in/out envelope
        envelope = np.ones_like(t)
        fade_samples = int(0.03 * SAMPLE_RATE)  # 30ms fade
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        
        audio = tone * envelope * 0.25  # Quieter than thinking sounds
        silence = np.zeros(int(0.08 * SAMPLE_RATE))  # 80ms gap
        
        tones.append(audio)
        tones.append(silence)
    
    return np.concatenate(tones)

def generate_sad_trombone():
    """Generate a subtle 'sad trombone' effect"""
    duration = 1.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Frequency drops from 440Hz to 200Hz
    freq_start = 440
    freq_end = 200
    frequency = np.linspace(freq_start, freq_end, len(t))
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    
    audio = np.sin(phase) * 0.2
    
    # Apply envelope
    envelope = np.exp(-t * 2)  # Exponential decay
    
    return audio * envelope

def generate_buzzer():
    """Generate a short error buzzer"""
    duration = 0.5
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Low frequency buzz
    freq = 100
    audio = np.sin(2 * np.pi * freq * t) * 0.3
    
    # Quick envelope
    envelope = np.ones_like(t)
    fade_samples = int(0.05 * SAMPLE_RATE)
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    return audio * envelope

def generate_gentle_negative():
    """Generate a gentle 'negative' sound"""
    duration = 0.6
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    # Two tones suggesting "no"
    freq1 = 523  # C
    freq2 = 392  # G
    
    # First tone
    t1 = t[:len(t)//2]
    tone1 = np.sin(2 * np.pi * freq1 * t1) * 0.2
    
    # Second tone
    t2 = t[len(t)//2:]
    tone2 = np.sin(2 * np.pi * freq2 * t2) * 0.2
    
    audio = np.concatenate([tone1, tone2])
    
    # Apply envelope
    envelope = np.ones_like(t)
    fade_samples = int(0.05 * SAMPLE_RATE)
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    return audio * envelope

def generate_single_beep():
    """Generate a single error beep"""
    duration = 0.3
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration))
    
    freq = 400  # Slightly lower than normal beeps
    audio = np.sin(2 * np.pi * freq * t) * 0.25
    
    # Quick fade
    envelope = np.ones_like(t)
    fade_samples = int(0.03 * SAMPLE_RATE)
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
    
    return audio * envelope

def main():
    """Generate all error sounds"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print("Generating error sounds...")
    
    # Generate various options
    sounds = {
        "error.wav": generate_descending_tones(),
        "error_trombone.wav": generate_sad_trombone(),
        "error_buzzer.wav": generate_buzzer(),
        "error_gentle.wav": generate_gentle_negative(),
        "error_beep.wav": generate_single_beep(),
    }
    
    for filename, audio in sounds.items():
        output_path = OUTPUT_DIR / filename
        sf.write(output_path, audio, SAMPLE_RATE)
        print(f"✓ Generated: {output_path}")
    
    print("\nGenerated error sounds:")
    print("  - error.wav (default) - Three descending tones")
    print("  - error_trombone.wav - Subtle sad trombone")
    print("  - error_buzzer.wav - Short buzzer")
    print("  - error_gentle.wav - Gentle negative indication")
    print("  - error_beep.wav - Single error beep")
    print("\nTo use a different sound, update ERROR_SOUND in .env")
    print("\nThese sounds indicate processing failures politely!")

if __name__ == "__main__":
    main()
