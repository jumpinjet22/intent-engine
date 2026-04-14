# Quick Start Guide

## 5-Minute Setup

### 1. Prerequisites
- ✅ NVIDIA GPU (RTX 2060 Super or better)
- ✅ Docker & Docker Compose installed
- ✅ MQTT broker with valid username/password credentials
- ✅ (Optional) UniFi Protect / G6 Entry doorbell integration
- ✅ (Optional) Frigate NVR integration

### 2. (Optional) Get UniFi Protect Credentials

**UniFi Protect API Token:**
```
1. Open UniFi Protect web interface
2. Go to Settings → Advanced → API
3. Click "Create Token"
4. Give it a name like "Doorbell Intent Engine"
5. Copy the token immediately (you won't see it again!)
```

**Camera ID:**
```
1. In UniFi Protect, click Devices
2. Click your G6 Entry camera
3. Look at the URL: /protect/devices/{THIS_IS_YOUR_CAMERA_ID}
4. Copy that ID
```

### 3. Configure

```bash
# Copy example config
cp .env.example .env

# Edit with your values
nano .env
```

**Minimum required:**
```bash
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_USERNAME=doorbell
MQTT_PASSWORD=changeme
```

> **Important:** `MQTT_USERNAME` and `MQTT_PASSWORD` cannot be empty. The intent engine fails startup validation if either value is blank.

**Optional integrations (not required for minimum boot):**
```bash
# UniFi Protect / doorbell integration
UNIFI_PROTECT_HOST=https://192.168.1.XXX
UNIFI_PROTECT_TOKEN=your_token_here
CAMERA_ID=your_camera_id_here

# Frigate integration
FRIGATE_HOST=http://192.168.1.XXX:5000
```

### 4. Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

This will:
- ✅ Check prerequisites
- ✅ Pull Docker images
- ✅ Download Llama 3.2 3B model
- ✅ Set everything up

### 5. Start the System

```bash
docker-compose up -d
```

### 6. Test It!

```bash
# Watch the logs
docker-compose logs -f intent-engine

# Now ring your doorbell and speak to it!
```

## What Should Happen

1. **Person detected** → Frigate sends event via MQTT
2. **Immediate acknowledgment** → "Hello!" or chime sound
3. **Wait for speech** → Camera listens for 5 seconds
4. **Transcription** → Whisper converts speech to text
5. **LLM response** → Ollama generates contextual reply
6. **TTS & playback** → XTTS synthesizes speech and plays through doorbell

**Expected latency:** 2-3 seconds from end of speech to response

## First Interaction Example

**You:** "Hi, I'm here to deliver a package"

**System:** 
- Detects person + package (Frigate)
- Hears "deliver a package" (Whisper)
- Generates: "Great! Please leave the package by the door. Thank you!"
- Plays response through doorbell speaker

## Monitoring

### Web UI
```
http://localhost:8080
```

### Logs
```bash
# All services
docker-compose logs -f

# Just intent engine
docker-compose logs -f intent-engine

# Just Ollama
docker-compose logs -f ollama
```

### Test Individual Components

**Test Ollama:**
```bash
docker exec -it doorbell-ollama ollama run llama3.2:3b "Say hello"
```

**Test MQTT:**
```bash
docker-compose logs mqtt
```

**Check GPU usage:**
```bash
watch -n 1 nvidia-smi
```

## Common First-Time Issues

### Issue: "Missing required MQTT credentials: MQTT_USERNAME"
**Fix:** Set a non-empty value for `MQTT_USERNAME` in `.env`.

### Issue: "Missing required MQTT credentials: MQTT_PASSWORD"
**Fix:** Set a non-empty value for `MQTT_PASSWORD` in `.env`.

### Issue: "Missing required MQTT credentials: MQTT_USERNAME, MQTT_PASSWORD"
**Fix:** Set both `MQTT_USERNAME` and `MQTT_PASSWORD` in `.env` (empty strings are treated as missing).

### Issue: "CUDA error: out of memory"
**Fix:** Use a smaller model:
```bash
# In .env
LLM_MODEL=llama3.2:1b
WHISPER_MODEL=tiny
```

### Issue: "No audio playing through doorbell"
**Fix:** 
1. Check logs for talkback session creation
2. Verify camera supports two-way audio
3. Test with a pre-recorded sound file first

### Issue: "Frigate events not triggering"
**Fix:**
1. Make sure Frigate is configured to detect people
2. Set up a zone called "entry" or "door" in Frigate
3. Check MQTT connection: `docker-compose logs mqtt`

> **Note:** Frigate is optional for minimum startup. If you're only validating a basic boot, you can skip Frigate event wiring until later.

## Performance Tips

### Faster Response Time

1. **Use smaller models:**
   ```bash
   LLM_MODEL=llama3.2:1b  # Faster
   WHISPER_MODEL=base     # Good balance
   TTS_ENGINE=piper       # Fastest TTS
   ```

2. **Reduce capture timeout:**
   ```bash
   RESPONSE_TIMEOUT=3  # Wait only 3 seconds for speech
   ```

3. **Pre-load models:**
   - Edit `intent_engine.py`
   - Keep all models in memory (requires more VRAM)

### Better Quality

1. **Use larger models:**
   ```bash
   LLM_MODEL=llama3.2:3b  # Better responses
   WHISPER_MODEL=small    # Better transcription
   TTS_ENGINE=xtts        # Most natural speech
   ```

2. **Enable voice cloning:**
   ```bash
   ENABLE_VOICE_CLONING=true
   # Record your voice and save as config/voice_sample.wav
   ```

## Next Steps

1. **Customize prompts** - Edit `intent_engine.py` → `build_prompt()`
2. **Add intent classification** - Detect specific visitor types
3. **Connect to Home Assistant** - Trigger automations
4. **Add more cameras** - Support multiple doorbells
5. **Train custom voice** - Clone a specific person's voice

## Getting Help

1. Check logs: `docker-compose logs -f intent-engine`
2. Enable debug: `DEBUG=true` in `.env`
3. Review README.md for detailed docs
4. Check UniFi Protect API is accessible

## Quick Commands Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# Restart just intent engine
docker-compose restart intent-engine

# View logs (follow)
docker-compose logs -f intent-engine

# Check status
docker-compose ps

# Pull new model
docker exec doorbell-ollama ollama pull llama3.2:1b

# Shell into container
docker exec -it doorbell-intent-engine bash

# Clean up everything
docker-compose down -v
```

Enjoy your AI-powered doorbell! 🔔🤖
