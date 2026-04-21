# Doorbell Intent Engine - Docker Setup
[![Build & Push Docker Images](https://github.com/jumpinjet22/intent-engine/actions/workflows/docker-image.yml/badge.svg)](https://github.com/jumpinjet22/intent-engine/actions/workflows/docker-image.yml)

A complete AI-powered doorbell system using Frigate, UniFi G6 Entry, Ollama, and local TTS.
## 🤝 Contributing

This project is still experimental and very much a work in progress. It kinda works (like the web GUI works and thats about it), but there are definitely rough edges and things that could be improved.

If you run into bugs, strange behavior, or have ideas for features or improvements, feel free to open an issue or submit a pull request.

Contributions of all kinds are welcome:
- Bug fixes
- Performance improvements
- New features or integrations
- Documentation cleanup (seriously, this helps a lot)

If you enjoy taking something that mostly works and making it solid, you’ll fit right in.

Let’s turn this from “it works on my machine” into something more reliable for everyone.
## Features

- 🤖 **LLM-powered responses** using Ollama (Llama 3.2)
- 🎤 **Speech recognition** with Whisper
- 🔊 **Text-to-speech** with XTTS, Piper, or Kokoro
- 📦 **Package detection** via Frigate integration
- 🏠 **Context-aware** responses based on time, visitor type
- 🔒 **Privacy-focused** - everything runs locally on your hardware
- ⚡ **Streaming responses** - low latency with sentence-by-sentence TTS

## Prerequisites

### Hardware
- NVIDIA GPU (RTX 2060 Super or better recommended)
  - Minimum 8GB VRAM
  - CUDA support required
- UniFi G6 Entry doorbell camera
- Machine running Docker with GPU support

### Software
- Docker & Docker Compose
- NVIDIA Container Toolkit
- Frigate NVR (running separately or in this stack)
- UniFi Protect controller

## Quick Start

### 1. Clone/Download this directory

```bash
cd doorbell-intent-engine
```

### 2. Configure environment variables

```bash
cp .env.example .env
nano .env
```

**Required settings:**
```bash
MQTT_HOST=localhost
MQTT_PORT=1883
```

**MQTT authentication is required.** Provide credentials either via environment variables
(`MQTT_USERNAME` / `MQTT_PASSWORD`) or Docker secrets (`MQTT_USERNAME_FILE` / `MQTT_PASSWORD_FILE`).

**Docker Hub images (recommended for deployment):**
```bash
INTENT_ENGINE_IMAGE=jumpnjet22/intent-engine:latest
WEB_UI_IMAGE=jumpnjet22/web-ui:latest
```

**Docker secrets setup (recommended):**
```bash
cp secrets/mqtt_username.txt.example secrets/mqtt_username.txt
cp secrets/mqtt_password.txt.example secrets/mqtt_password.txt
```

**To get your UniFi Protect API token:**
1. Log into UniFi Protect
2. Go to Settings → Advanced → API
3. Create a new API token with camera access

**To get your camera ID:**
1. In UniFi Protect, go to Devices
2. Click on your G6 Entry
3. The ID is in the URL: `/protect/devices/{CAMERA_ID}`

### 3. Install NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

### 4. Add acknowledgment sound (optional)

Place a `chime.wav` file in the `sounds/` directory for immediate doorbell acknowledgment:

```bash
cp /path/to/your/chime.wav sounds/
```

Or the system will generate a quick "Hello!" using TTS.

### 5. Start the stack

```bash
# First time - pull Ollama model
docker-compose up ollama -d
docker exec -it doorbell-ollama ollama pull llama3.2:3b

# Optional: pre-pull published Docker Hub images
docker pull jumpnjet22/intent-engine:latest
docker pull jumpnjet22/web-ui:latest

# Start all services
docker-compose up -d

# Start all services with Docker secrets override (recommended)
docker compose -f docker-compose.yml -f docker-compose.secrets.yml up -d

# Web UI path A (local development build from ./web-ui)
docker compose up -d --build web-ui

# Web UI path B (prebuilt image from WEB_UI_IMAGE)
WEB_UI_IMAGE=jumpnjet22/web-ui:latest docker compose pull web-ui && \
WEB_UI_IMAGE=jumpnjet22/web-ui:latest docker compose up -d web-ui

# View logs
docker-compose logs -f intent-engine
```

`web-ui` in both `docker-compose.yml` and `docker-compose.min.yml` defines **both** `build` and
`image`. Runtime behavior is:

- `docker compose up web-ui` uses an existing local image tag (or pulls the `image` tag if missing).
- `docker compose up --build web-ui` forces a rebuild from `./web-ui` and tags it as `WEB_UI_IMAGE`
  (or `jumpnjet22/web-ui:latest` when `WEB_UI_IMAGE` is unset).

Use `--build` when you are actively changing files in `./web-ui`; use `WEB_UI_IMAGE` + `pull` when
you want a published prebuilt image.

## Configuration

### TTS Engine Selection

Edit `.env` to choose your TTS engine:

```bash
# Options: xtts, piper, kokoro
TTS_ENGINE=xtts
```

**Recommendations:**
- **XTTS**: Best quality, closest to ElevenLabs (~1.5s latency)
- **Piper**: Fast and efficient (~0.5s latency)
- **Kokoro**: Good balance (~0.8s latency)

### Voice Cloning (XTTS only)

To clone a voice:

1. Record 6-10 seconds of clean speech
2. Save as `voice_sample.wav` in `config/`
3. Enable in `.env`:

```bash
ENABLE_VOICE_CLONING=true
```

### Whisper Model Selection

Trade off between speed and accuracy:

```bash
# Options: tiny, base, small, medium, large
WHISPER_MODEL=base  # Recommended for RTX 2060 Super
```

### LLM Model Selection

```bash
# Options: llama3.2:1b, llama3.2:3b, llama3.1:8b, etc.
LLM_MODEL=llama3.2:3b  # Best balance for 8GB VRAM
```

### MQTT Topics

The intent engine subscribes to:

- `frigate/events`
- `doorbell/doorbell_press`
- `doorbell/human_active`
- `doorbell/dialogue/answer`

It publishes:

- `doorbell/session/state`
- `doorbell/intent`
- `doorbell/tts/request`
- `doorbell/tts/status`
- `doorbell/escalate`

See `.env.example` for topic overrides.

### MQTT Authentication (Required)

The intent engine requires `MQTT_USERNAME` and `MQTT_PASSWORD` on startup. If you use the bundled
Mosquitto container, create a password file and disable anonymous access in `mosquitto.conf` before
starting the stack.

### Web UI image/build mode

The `web-ui` service is intentionally configured the same way in both compose files:

- `docker-compose.yml`
- `docker-compose.min.yml`

Each has both:

- `build: ./web-ui`
- `image: ${WEB_UI_IMAGE:-jumpnjet22/web-ui:latest}`

Pick one workflow:

1. **Local development build (recommended when editing UI code):**

   ```bash
   docker compose up -d --build web-ui
   ```

2. **Prebuilt image workflow (recommended for stable deployments):**

   ```bash
   WEB_UI_IMAGE=jumpnjet22/web-ui:latest docker compose pull web-ui && WEB_UI_IMAGE=jumpnjet22/web-ui:latest docker compose up -d web-ui
   ```

If you do not pass `--build`, Compose will not force a rebuild of `./web-ui`; it will run the image
tag resolved by `WEB_UI_IMAGE` (pulling it if needed).

## Architecture

```
┌─────────────┐
│   Frigate   │ ──(MQTT)──┐
└─────────────┘           │
                          ▼
┌─────────────┐     ┌──────────────┐
│  G6 Entry   │────▶│ Intent Engine │
│  (Camera)   │     │              │
└─────────────┘     │  • Whisper   │
      ▲             │  • Ollama    │
      │             │  • TTS       │
      │             └──────────────┘
      │                     │
      └─────────────────────┘
       (Audio Response)
```

## Integration with Frigate

If you already have Frigate running elsewhere:

1. Set `FRIGATE_HOST` in `.env` to your Frigate IP
2. Set `MQTT_HOST` to your existing MQTT broker (or use the included one)
3. Comment out the Frigate service in `docker-compose.yml`

If Frigate is running on the same Docker network:

```bash
FRIGATE_HOST=frigate
MQTT_HOST=mqtt
```

## Monitoring

### Web UI (Optional)

Access the monitoring dashboard at `http://localhost:8080`

- View recent events
- Test audio output
- Monitor system status
- Adjust settings

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f intent-engine

# Real-time Ollama
docker-compose logs -f ollama
```

## Performance Tuning

### GPU Memory Issues

If you run out of VRAM:

1. Use smaller models:
   ```bash
   LLM_MODEL=llama3.2:1b
   WHISPER_MODEL=tiny
   ```

2. Sequential model loading (edit `intent_engine.py`):
   - Load Whisper → transcribe → unload
   - Load Llama → generate → unload
   - Load TTS → synthesize → unload

### Latency Optimization

Current typical latency breakdown:
```
Frigate detection:    ~200ms
Acknowledgment:       ~500ms (pre-recorded)
Audio capture:        5s (configurable)
Whisper:              ~800ms
First LLM tokens:     ~300ms
First TTS output:     ~1.5s (XTTS)
----------------------------
Total response time:  ~2.3s after visitor stops speaking
```

To reduce latency:

1. Use streaming (already implemented)
2. Reduce `RESPONSE_TIMEOUT` for faster capture
3. Use faster models (Piper TTS, Llama 3.2 1B)
4. Pre-load all models in memory (if you have VRAM)

## Troubleshooting

### "No GPU found"

```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Ollama connection failed

```bash
# Check Ollama is running
docker-compose ps ollama

# Test Ollama
docker exec -it doorbell-ollama ollama list
```

### UniFi Protect connection issues

```bash
# Test API access
curl -k -H "Authorization: Bearer YOUR_TOKEN" \
  https://YOUR_PROTECT_IP/api/bootstrap
```

### Audio not playing

1. Check talkback session creation in logs
2. Verify camera supports talkback (G6 Entry does)
3. Test with a simple audio file first

### Frigate events not triggering

1. Verify MQTT connection:
   ```bash
   docker-compose logs mqtt
   ```

2. Subscribe to Frigate events manually:
   ```bash
   mosquitto_sub -h localhost -t "frigate/#" -v
   ```

3. Check camera name matches in Frigate config

## Advanced Configuration

### Custom Prompts

Edit `intent_engine.py`, `build_prompt()` method to customize LLM behavior.

### Intent Classification

Add custom intent detection in `extract_frigate_context()`:

```python
# Detect specific scenarios
if context['has_package'] and 'delivery' in transcript.lower():
    context['intent'] = 'package_delivery'
elif 'pizza' in transcript.lower():
    context['intent'] = 'food_delivery'
```

### Multiple Cameras

To handle multiple G6 Entry cameras:

1. Duplicate the intent-engine service in docker-compose
2. Set different `CAMERA_ID` for each
3. Filter by camera name in `should_process_event()`

## System Requirements

### Minimum
- RTX 2060 Super (8GB VRAM)
- 16GB RAM
- 50GB disk space

### Recommended
- RTX 3060 or better (12GB+ VRAM)
- 32GB RAM
- 100GB disk space (for model storage and logs)

## Cost Comparison

Running locally vs cloud APIs (100 doorbell events/month):

| Service | Local Cost | Cloud Cost |
|---------|-----------|------------|
| **LLM** | $0 | $2.00 (OpenAI) |
| **TTS** | $0 | $1.50 (ElevenLabs) |
| **STT** | $0 | $0.50 (Whisper API) |
| **Electricity** | ~$1.50 | $0 |
| **Total** | **$1.50/mo** | **$4.00/mo** |

Plus: Complete privacy, no internet dependency, unlimited usage

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f intent-engine`
2. Enable debug mode: `DEBUG=true` in `.env`
3. Review UniFi Protect API docs
4. Check Frigate integration

## License

MIT License - Use freely for personal or commercial projects

## Credits

- **Ollama** - LLM inference
- **Faster Whisper** - Speech recognition
- **Coqui TTS / Piper** - Text-to-speech
- **Frigate** - NVR and object detection
- **Ubiquiti** - G6 Entry hardware
