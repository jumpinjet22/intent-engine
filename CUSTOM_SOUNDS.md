# Custom Sounds & Audio Conversion Guide

## Overview

The doorbell system automatically converts your custom audio files to the correct format for UniFi talkback. You can use **any audio format** and the system handles conversion!

## Supported Input Formats

✅ **Anything FFmpeg supports:**
- WAV (any sample rate, any bit depth)
- MP3
- M4A / AAC
- FLAC
- OGG
- OPUS
- And many more!

The system automatically:
1. Detects your camera's required format
2. Converts your audio to match
3. Streams to the doorbell speaker

## Adding Your Custom Sounds

### 1. Create or Record Your Sounds

**Record Your Own:**
```bash
# Using your phone's voice recorder
# Or using Audacity on computer
# Or any recording software
```

**Download Royalty-Free Sounds:**
- Freesound.org
- Zapsplat.com  
- Soundbible.com

### 2. Place in sounds/ Directory

```bash
# Copy your custom sounds
cp my_custom_chime.mp3 sounds/
cp my_thinking_sound.wav sounds/
cp my_error_sound.m4a sounds/
```

### 3. Update .env Configuration

```bash
# .env
ACKNOWLEDGMENT_SOUND=my_custom_chime.mp3
THINKING_SOUND=my_thinking_sound.wav
ERROR_SOUND=my_error_sound.m4a
```

That's it! The system handles all conversion automatically.

## How Audio Conversion Works

### UniFi Talkback Requirements

When you create a talkback session, UniFi Protect tells you:
```json
{
  "url": "rtsps://camera-ip:7441/...",
  "codec": "AAC",                    // or "PCM"
  "samplingRate": 16000,             // Hz
  "bitsPerSample": 16                // bits
}
```

### Automatic Conversion Process

```
Your File (MP3, 44100Hz, stereo)
         ↓
FFmpeg Conversion
         ↓
Camera Format (AAC, 16000Hz, mono)
         ↓
Stream to Camera
```

**The system automatically:**
- Detects source format
- Resamples to camera's sample rate
- Converts stereo → mono
- Encodes to camera's codec (AAC or PCM)
- Adjusts bit depth
- Normalizes volume

## Sound Requirements

### What Makes a Good Doorbell Sound?

**Duration:**
- Acknowledgment: 0.5-2 seconds
- Thinking: 0.5-2 seconds  
- Error: 0.5-1.5 seconds

**Volume:**
- Should be clear but not startling
- -6dB to -12dB is good range
- System normalizes automatically

**Frequency:**
- 200Hz-4000Hz range works best
- Avoid very high frequencies (>8kHz)
- Human voice range is ideal

**Format:**
- Mono preferred (stereo converted automatically)
- Any sample rate works (will be resampled)
- Any bit depth works

### Testing Your Sounds

```bash
# Play sound locally to test
ffplay -nodisp -autoexit sounds/my_custom_sound.mp3

# Check audio properties
ffprobe -i sounds/my_custom_sound.mp3

# Test conversion (see what camera will receive)
ffmpeg -i sounds/my_custom_sound.mp3 \
  -ar 16000 -ac 1 -acodec aac \
  sounds/test_converted.aac
  
ffplay -nodisp -autoexit sounds/test_converted.aac
```

## Example Custom Sounds

### 1. Voice Acknowledgment

Record yourself saying:
- "Hello, one moment please"
- "Hi there!"
- "Welcome!"
- Custom business greeting

```bash
# Record on your phone
# Transfer to computer
cp ~/Downloads/greeting.m4a sounds/acknowledgment_voice.m4a

# Update .env
ACKNOWLEDGMENT_SOUND=acknowledgment_voice.m4a
```

### 2. Branded Sounds

Use your company's:
- Brand jingle
- Logo sound
- Custom audio branding

### 3. Multilingual Options

```bash
# Different sounds for different contexts
sounds/greeting_english.wav
sounds/greeting_spanish.wav
sounds/greeting_french.wav
```

Configure in code based on context or time of day.

### 4. Seasonal Sounds

```bash
sounds/christmas_chime.mp3
sounds/halloween_greeting.wav
sounds/summer_greeting.mp3
```

Switch automatically based on calendar!

## Audio Editing Tips

### Using Audacity (Free)

**Normalize Volume:**
1. Open your audio file
2. Effect → Normalize
3. Set to -3dB
4. Export

**Add Fade In/Out:**
1. Select beginning (50-100ms)
2. Effect → Fade In
3. Select ending (50-100ms)
4. Effect → Fade Out
5. Export

**Adjust Length:**
1. Use Time Shift Tool
2. Drag to desired length
3. Use Ctrl+T to truncate
4. Export

**Remove Background Noise:**
1. Select noise profile section
2. Effect → Noise Reduction
3. Get Noise Profile
4. Select all
5. Effect → Noise Reduction → Apply

### Using FFmpeg Command Line

**Trim audio:**
```bash
ffmpeg -i input.mp3 -ss 0 -t 2 -c copy output.mp3
```

**Change volume:**
```bash
ffmpeg -i input.mp3 -filter:a "volume=0.5" output.mp3
```

**Add fade:**
```bash
ffmpeg -i input.mp3 -af "afade=t=in:st=0:d=0.1,afade=t=out:st=1.9:d=0.1" output.mp3
```

**Convert format:**
```bash
ffmpeg -i input.m4a -acodec libmp3lame -b:a 192k output.mp3
```

**Combine sounds:**
```bash
# Concatenate multiple sounds
ffmpeg -i sound1.mp3 -i sound2.mp3 \
  -filter_complex "[0:0][1:0]concat=n=2:v=0:a=1" output.mp3
```

## Advanced: Context-Aware Sounds

### Dynamic Sound Selection

Edit `intent_engine.py`:

```python
async def play_acknowledgment(self):
    """Play context-aware acknowledgment"""
    
    hour = datetime.now().hour
    
    # Time-based selection
    if 6 <= hour < 12:
        sound_file = "greeting_morning.mp3"
    elif 12 <= hour < 18:
        sound_file = "greeting_afternoon.mp3"
    elif 18 <= hour < 22:
        sound_file = "greeting_evening.mp3"
    else:
        sound_file = "greeting_quiet.mp3"  # Quieter for night
    
    sound_path = self.config.sounds_dir / sound_file
    await self.unifi_handler.play_audio_file(sound_path)
```

### Language Detection

```python
async def play_acknowledgment_for_language(self, detected_language):
    """Play greeting in detected language"""
    
    language_sounds = {
        'en': 'greeting_english.mp3',
        'es': 'greeting_spanish.mp3',
        'fr': 'greeting_french.mp3',
        'de': 'greeting_german.mp3',
    }
    
    sound_file = language_sounds.get(detected_language, 'greeting_english.mp3')
    sound_path = self.config.sounds_dir / sound_file
    await self.unifi_handler.play_audio_file(sound_path)
```

### Visitor Type Based

```python
async def play_context_sound(self, context):
    """Play different sounds based on visitor type"""
    
    if context.get('has_package'):
        sound = "greeting_delivery.mp3"
    elif context.get('expected_guest'):
        sound = "greeting_welcome.mp3"
    elif context.get('after_hours'):
        sound = "greeting_closed.mp3"
    else:
        sound = "greeting_default.mp3"
    
    await self.unifi_handler.play_audio_file(
        self.config.sounds_dir / sound
    )
```

## Troubleshooting Audio Issues

### Sound Not Playing

**Check file exists:**
```bash
ls -la sounds/
```

**Test file is valid:**
```bash
ffplay -nodisp -autoexit sounds/your_sound.mp3
```

**Check logs:**
```bash
docker-compose logs -f intent-engine | grep -i audio
```

### Sound Too Quiet

**Increase volume:**
```bash
ffmpeg -i sounds/quiet.mp3 \
  -filter:a "volume=2.0" \
  sounds/louder.mp3
```

### Sound Too Loud/Distorted

**Decrease volume:**
```bash
ffmpeg -i sounds/loud.mp3 \
  -filter:a "volume=0.5" \
  sounds/quieter.mp3
```

**Normalize:**
```bash
ffmpeg -i sounds/loud.mp3 \
  -filter:a "loudnorm" \
  sounds/normalized.mp3
```

### Wrong Format/Not Converting

The system should handle all formats automatically. If you have issues:

**Check FFmpeg is working:**
```bash
docker exec doorbell-intent-engine ffmpeg -version
```

**Manually test conversion:**
```bash
docker exec doorbell-intent-engine ffmpeg \
  -i /app/sounds/your_file.mp3 \
  -ar 16000 -ac 1 -acodec aac \
  /app/cache/test_output.aac
```

### Conversion Taking Too Long

For very large files, pre-convert them:

```bash
ffmpeg -i large_file.wav \
  -ar 16000 -ac 1 -acodec aac -b:a 64k \
  optimized_file.aac
```

## Sound Library Structure

Organize your sounds:

```
sounds/
├── acknowledgments/
│   ├── morning.mp3
│   ├── afternoon.mp3
│   ├── evening.mp3
│   └── night.mp3
├── thinking/
│   ├── default.wav
│   ├── quick.wav
│   └── processing.wav
├── errors/
│   ├── gentle.mp3
│   └── technical.mp3
├── languages/
│   ├── en_hello.mp3
│   ├── es_hola.mp3
│   └── fr_bonjour.mp3
└── seasonal/
    ├── christmas.mp3
    ├── halloween.mp3
    └── newyear.mp3
```

## Performance Considerations

**Conversion Speed:**
- First playback: ~100-300ms conversion time
- Can pre-convert if needed
- Async operation doesn't block LLM

**File Size:**
- Keep sounds under 5MB
- System will convert efficiently
- Smaller is better for speed

**Quality vs Size:**
- 16kHz sample rate is plenty for doorbell
- Mono is sufficient
- AAC at 64kbps is good quality

## Best Practices

1. **Test Before Deploying**
   - Play sounds locally first
   - Test with real doorbell
   - Check volume levels

2. **Backup Your Sounds**
   - Keep originals separate
   - Version control if customizing

3. **Document Your Sounds**
   - Note what each file is for
   - Keep README in sounds/

4. **Consider Accessibility**
   - Avoid very high/low frequencies
   - Clear, distinct sounds
   - Not too loud or startling

5. **Brand Consistency**
   - Match your brand voice
   - Professional quality
   - Consistent volume levels

## Examples from the Community

### Home Use
- Kids' voices: "Daddy's working, mom will be right there!"
- Pet sounds: Friendly bark, meow
- Family inside jokes

### Business Use
- Company jingle
- Professional greeting
- Operating hours message

### Creative Use
- Movie quotes (public domain)
- Sound effects from games
- Musical instruments

## Resources

**Free Sound Libraries:**
- Freesound.org (CC licenses)
- Zapsplat.com (free tier)
- BBC Sound Effects
- YouTube Audio Library

**Audio Tools:**
- Audacity (free, open source)
- Ocenaudio (free, simple)
- Reaper (pro, affordable)
- FFmpeg (command line)

**Text-to-Speech for Custom Greetings:**
- Google Cloud TTS
- Amazon Polly
- Microsoft Azure TTS
- Coqui TTS (local)

---

**Pro Tip:** Record your acknowledgment sound in the same voice/style as your TTS engine for a cohesive experience!
