# New Features - MQTT Triggers & Multi-Camera Support

## What's New

### 🎯 MQTT Trigger Support
- Trigger doorbell responses from **any MQTT source**
- Perfect for **Home Assistant** automations
- Works with **dumb doorbells** (add AI to existing hardware)
- **No Frigate required** for manual triggers

### 📹 Multi-Camera Dashboard
- **Visual camera selection** from UniFi Protect
- See all cameras with speaker/mic support
- **One-click testing** from web interface
- Works with **any UniFi camera**, not just doorbells

### 🎨 Enhanced Web UI
- Beautiful new dashboard design
- Camera list with status badges
- Manual trigger interface
- Real-time event monitoring
- MQTT integration examples

## Quick Start

### 1. Update Your .env File

Add these new lines:

```bash
# MQTT Trigger Support
ENABLE_MQTT_TRIGGERS=true
MQTT_TRIGGER_TOPIC=doorbell/doorbell_press

# Multi-camera support
ENABLE_MULTI_CAMERA=true
```

### 2. Restart Services

```bash
docker-compose down
docker-compose up -d
```

### 3. Open New Dashboard

Navigate to: `http://localhost:8080`

You'll see:
- Camera list from UniFi Protect
- Manual trigger controls
- Event history

## Home Assistant Integration

### Quick Setup

1. Add to your `automations.yaml`:

```yaml
- alias: "Doorbell Pressed - AI Response"
  trigger:
    - platform: state
      entity_id: binary_sensor.your_doorbell
      to: "on"
  action:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "YOUR_CAMERA_ID",
            "source": "home_assistant"
          }
```

2. Get your camera ID from the web dashboard at `http://localhost:8080`

3. Test it by pressing your doorbell!

## Use Cases

### 1. Dumb Doorbell → Smart Response

Connect your existing doorbell button to:
- ESP32/ESP8266
- Raspberry Pi GPIO
- Shelly relay
- Any MQTT-capable device

When pressed → Sends MQTT → AI responds through camera

### 2. Multiple Cameras

Use any camera with speaker/mic:
- Front door
- Back door
- Garage
- Office entrance

Select different camera for each location in the dashboard.

### 3. Time-Based Responses

Home Assistant automation:
- Daytime: Normal greeting
- Nighttime: "Please come back during business hours"
- Lunch time: "We're currently closed for lunch"

### 4. Package Detection

Frigate detects package + person → MQTT trigger → Special delivery greeting

## Testing

### Using the Dashboard

1. Open `http://localhost:8080`
2. Click on a camera to select it
3. Choose "Manual Test" as source
4. Click "Trigger Doorbell Response"
5. Watch the logs: `docker-compose logs -f intent-engine`

### Using Command Line

```bash
# Publish MQTT trigger
mosquitto_pub -h localhost -t "doorbell/doorbell_press" -m '{
  "camera_id": "your_camera_id",
  "source": "test"
}'
```

### Using Home Assistant

Developer Tools → Services:
```yaml
service: mqtt.publish
data:
  topic: doorbell/doorbell_press
  payload: '{"camera_id":"xyz","source":"ha_test"}'
```

## Camera Requirements

To use a camera with the intent engine:

✅ **Required:**
- Two-way audio (speaker + microphone)
- RTSP stream
- Listed in UniFi Protect

✅ **Compatible Models:**
- G6 Entry (recommended)
- G4 Doorbell Pro
- AI Pro
- G3 Instant (with mic)
- Any UniFi camera with audio I/O

❌ **Not Compatible:**
- Cameras without speakers
- View-only cameras
- Cameras without microphone

Check the dashboard to see which of your cameras are compatible!

## Architecture

```
┌──────────────────┐
│  Home Assistant  │
│   Dumb Doorbell  │
│   Any MQTT Device│
└────────┬─────────┘
         │
         ▼
    MQTT Publish
         │
         ▼
┌────────────────┐      ┌─────────────┐
│  MQTT Broker   │◄────►│   Web UI    │
│  (Mosquitto)   │      │  Dashboard  │
└────────┬───────┘      └─────────────┘
         │
         ▼
┌────────────────┐
│ Intent Engine  │
│                │
│ • Whisper STT  │
│ • Ollama LLM   │
│ • XTTS TTS     │
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ Selected Camera│
│  (Any with A/V)│
└────────────────┘
```

## Troubleshooting

### Camera List Empty

1. Check UniFi Protect credentials in `.env`
2. Verify network access to Protect controller
3. Check web UI logs: `docker-compose logs web-ui`

### MQTT Trigger Not Working

1. Check MQTT broker: `docker-compose logs mqtt`
2. Subscribe to test: `mosquitto_sub -h localhost -t "doorbell/#" -v`
3. Enable debug: Set `DEBUG=true` in `.env`

### Home Assistant Not Connecting

1. Verify MQTT broker IP in HA config
2. Test with mosquitto_pub first
3. Check HA MQTT integration status

## Advanced Configuration

### Custom MQTT Topics

```bash
# .env
MQTT_TRIGGER_TOPIC=home/doorbell/doorbell_press
```

### Multiple Locations

Create separate Home Assistant automations for each doorbell, each publishing with different camera IDs.

### Context-Aware Responses

Pass custom context in MQTT payload:

```json
{
  "camera_id": "xyz",
  "source": "home_assistant",
  "context": {
    "location": "front_door",
    "time_of_day": "evening",
    "expected_guest": "John Smith",
    "custom_prompt": "Welcome! The door is unlocked."
  }
}
```

## Documentation

- **Full MQTT Guide:** See `MQTT_INTEGRATION.md`
- **Main README:** See `README.md`
- **Quick Start:** See `QUICKSTART.md`

## What's Next?

Planned features:
- [ ] Face recognition integration
- [ ] Custom voice profiles per location
- [ ] Scheduled responses
- [ ] Integration with smart locks
- [ ] Mobile app for monitoring
- [ ] Cloud sync (optional)

## Feedback

Having issues or ideas? 
1. Check logs: `docker-compose logs -f`
2. Enable debug mode in `.env`
3. Review `MQTT_INTEGRATION.md` for detailed examples

Enjoy your expanded doorbell system! 🎉
