# Thinking Sounds Feature

## Overview

The thinking sound feature plays a pleasant audio cue while the system processes the visitor's speech. This provides better user feedback and makes the interaction feel more natural.

## How It Works

**Timeline:**
```
1. Doorbell pressed → 🔔 Chime plays (instant)
2. Visitor speaks → 👂 System listens
3. Processing starts → 🎵 Thinking sound plays
4. Response ready → 🗣️ AI speaks response
```

**Processing includes:**
- Speech transcription (Whisper) - ~800ms
- LLM generation (Ollama) - ~300-500ms
- TTS synthesis (XTTS) - ~1000-1500ms

The thinking sound fills this gap and lets the visitor know the system is working.

## Configuration

### Enable/Disable

```bash
# .env
ENABLE_THINKING_SOUND=true  # or false
THINKING_SOUND=thinking.wav
```

### Sound Options

We provide several pre-generated sounds:

1. **thinking.wav** (default) - Three rising tones (A-C-E chord)
   - Duration: ~1 second
   - Friendly and professional
   - Recommended for most use cases

2. **thinking_hum.wav** - Gentle humming
   - Duration: ~1.5 seconds
   - Subtle and calming
   - Good for residential settings

3. **thinking_chirp.wav** - Quick chirp
   - Duration: ~0.4 seconds
   - Playful and quick
   - Good for fast responses

4. **thinking_beep.wav** - Soft beep
   - Duration: ~0.8 seconds
   - Simple and clear
   - Professional tone

5. **thinking_click.wav** - Subtle click
   - Duration: ~0.2 seconds
   - Mechanical/tech feel
   - Minimal distraction

## Generating Sounds

### Automatic Generation

```bash
# Generate all preset sounds
python3 generate_thinking_sounds.py
```

This creates all options in the `sounds/` directory.

### Custom Sounds

You can use any audio file! Just:

1. Create or record your sound
2. Convert to WAV format (16kHz, mono recommended)
3. Save as `sounds/thinking_custom.wav`
4. Update `.env`:
   ```bash
   THINKING_SOUND=thinking_custom.wav
   ```

### Using TTS Instead

For a more natural feel, use TTS phrases:

```python
# In intent_engine.py, modify play_thinking_sound():

async def play_thinking_sound(self):
    """Play thinking/processing sound"""
    phrases = [
        "One moment...",
        "Let me think...",
        "Just a second...",
        "Processing..."
    ]
    
    import random
    phrase = random.choice(phrases)
    await self.speak_text(phrase)
```

## Sound Design Tips

### Good Thinking Sounds Should Be:

✅ **Brief** - 0.5-2 seconds
✅ **Pleasant** - Not jarring or annoying
✅ **Clear** - Audible but not too loud
✅ **Professional** - Matches your brand/context
✅ **Non-verbal** - Or very short phrases

### Avoid:

❌ Long sounds (>3 seconds)
❌ Harsh/annoying tones
❌ Complex music or melodies
❌ Sounds that might scare/confuse visitors

## Examples by Context

### Residential Home
```bash
THINKING_SOUND=thinking_hum.wav
```
Gentle and calming for family/friends

### Business/Office
```bash
THINKING_SOUND=thinking_beep.wav
```
Professional and efficient

### Tech Startup
```bash
THINKING_SOUND=thinking_chirp.wav
```
Playful and modern

### Luxury/High-End
```bash
THINKING_SOUND=thinking.wav
```
Sophisticated three-tone sequence

## Advanced: Context-Aware Sounds

You can play different sounds based on context:

```python
# In intent_engine.py

async def play_thinking_sound(self, context: Dict = None):
    """Play context-aware thinking sound"""
    
    # Different sound based on time of day
    hour = datetime.now().hour
    
    if 22 <= hour or hour < 6:
        # Nighttime - quieter sound
        sound_path = self.config.sounds_dir / "thinking_quiet.wav"
    elif context and context.get('has_package'):
        # Delivery - quick professional sound
        sound_path = self.config.sounds_dir / "thinking_beep.wav"
    else:
        # Default
        sound_path = self.config.thinking_sound_path
    
    if sound_path.exists():
        await self.unifi_handler.play_audio_file(sound_path)
```

## Creating Custom Sounds

### Using Audacity

1. Generate Tone (Analyze → Tone Generator)
   - Frequency: 440-880 Hz
   - Duration: 0.5-1.5 seconds
   - Waveform: Sine (smoothest)

2. Apply Fade In/Out
   - Effect → Fade In (50ms)
   - Effect → Fade Out (50ms)

3. Adjust Volume
   - Effect → Amplify (-6 to -12 dB)

4. Export
   - File → Export → Export as WAV
   - 16-bit PCM, Mono, 16000 Hz

### Using Python (Advanced)

```python
import numpy as np
import soundfile as sf

# Create a pleasant arpeggio
duration = 1.0
sample_rate = 16000
t = np.linspace(0, duration, int(sample_rate * duration))

# Three note sequence
notes = [440, 523, 659]  # A, C, E
audio = np.zeros_like(t)

for i, freq in enumerate(notes):
    start = int(i * len(t) / 3)
    end = int((i + 1) * len(t) / 3)
    segment = t[start:end]
    tone = np.sin(2 * np.pi * freq * segment) * 0.3
    audio[start:end] = tone

# Fade in/out
fade = int(0.05 * sample_rate)
audio[:fade] *= np.linspace(0, 1, fade)
audio[-fade:] *= np.linspace(1, 0, fade)

# Save
sf.write('sounds/thinking_custom.wav', audio, sample_rate)
```

## Troubleshooting

### Sound Not Playing

1. Check if sound file exists:
   ```bash
   ls -la sounds/thinking.wav
   ```

2. Verify it's enabled:
   ```bash
   grep ENABLE_THINKING_SOUND .env
   ```

3. Check logs:
   ```bash
   docker-compose logs -f intent-engine | grep "thinking"
   ```

### Sound Too Quiet/Loud

Adjust volume with ffmpeg:

```bash
# Increase volume by 10dB
ffmpeg -i sounds/thinking.wav -filter:a "volume=10dB" sounds/thinking_louder.wav

# Decrease volume by 6dB
ffmpeg -i sounds/thinking.wav -filter:a "volume=-6dB" sounds/thinking_quieter.wav
```

### Wrong Duration

The thinking sound should roughly match your processing time:
- Fast system (~1s): Use short sounds (0.5-1s)
- Medium system (~2s): Use medium sounds (1-1.5s)
- Slow system (~3s+): Use longer sounds or loop

### Sound Format Issues

Convert to correct format:

```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 -acodec pcm_s16le sounds/thinking.wav
```

## Performance Impact

Thinking sounds have **minimal performance impact**:
- Played asynchronously (non-blocking)
- Small file sizes (10-50 KB)
- No GPU required
- Can play while LLM processes

## Disabling Feature

To completely disable:

```bash
# .env
ENABLE_THINKING_SOUND=false
```

Or delete the thinking sound file:

```bash
rm sounds/thinking.wav
```

The system will continue without it.

## Best Practices

1. **Test with real visitors** - What sounds professional to you might annoy others
2. **Keep it short** - Under 2 seconds is ideal
3. **Match your brand** - Tech company vs. residential vs. business
4. **Consider accessibility** - Some people are sensitive to certain tones
5. **Have variations** - Different sounds for day/night, different contexts

## Integration with Other Features

### With Voice Cloning

If you're using voice cloning, consider having the thinking "sound" be a TTS phrase in that voice:

```python
# Custom thinking phrase in cloned voice
await self.speak_text("One moment, let me think...")
```

### With Home Assistant

Trigger different thinking sounds based on who's at the door:

```yaml
- service: mqtt.publish
  data:
    topic: doorbell/doorbell_press
    payload: >
      {
        "camera_id": "xyz",
        "context": {
          "thinking_sound": "thinking_hum.wav",
          "expected_guest": true
        }
      }
```

## Future Enhancements

Planned features:
- [ ] Random selection from sound pool
- [ ] Adaptive duration based on processing time
- [ ] Voice-based thinking phrases with personality
- [ ] Learning which sounds work best
- [ ] Time-of-day automatic selection

---

**Pro Tip:** The default three-tone sequence was specifically designed to be pleasant, professional, and universally recognizable as "processing" without being annoying!
