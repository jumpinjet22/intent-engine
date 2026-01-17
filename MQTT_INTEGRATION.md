# MQTT Integration Guide

## Overview

The doorbell intent engine supports MQTT triggers, allowing you to integrate with:
- **Home Assistant** - Automate doorbell responses
- **Dumb doorbells** - Add AI to existing hardware
- **Any MQTT-enabled device** - Maximum flexibility
- **Multiple cameras** - Use any camera with speaker/mic, not just G6 Entry

## Architecture

```
┌─────────────────┐
│ Home Assistant  │
│  (or any MQTT)  │
└────────┬────────┘
         │ MQTT Publish
         ▼
┌─────────────────┐
│  MQTT Broker    │
│  (Mosquitto)    │
└────────┬────────┘
         │ doorbell/doorbell_press
         ▼
┌─────────────────┐
│ Intent Engine   │
│                 │
│ Processes just  │
│ like a Frigate  │
│ event           │
└─────────────────┘

## "Thought" Debug Logging (Optional)

If you want the engine to log what it *saw* and the decisions it made (without changing your MQTT topics), enable structured JSONL logging.

### Environment Variables

- `THOUGHT_LOG_ENABLED=true` – turn logging on
- `THOUGHT_LOG_PATH=/data/thinking.log.jsonl` – where to write logs (recommended to mount `/data` as a volume)
- `THOUGHT_LOG_INCLUDE_TRANSCRIPT=false` – include the visitor transcript in the log (off by default)
- `THOUGHT_LOG_REDACT_PII=true` – redact phone numbers/emails if transcripts/responses are logged

### Example

```bash
tail -f ./data/thinking.log.jsonl | jq
```
```

## MQTT Trigger Format

### Basic Trigger

```json
{
  "camera_id": "66d025b301ebc903e80003ea",
  "camera_name": "Front Door Camera",
  "source": "home_assistant"
}
```

### Advanced Trigger with Context

```json
{
  "camera_id": "66d025b301ebc903e80003ea",
  "camera_name": "Front Door Camera",
  "source": "dumb_doorbell",
  "context": {
    "trigger_type": "doorbell_press",
    "location": "front_door",
    "custom_prompt": "Someone pressed the doorbell",
    "time_of_day": "evening"
  }
}
```

## Human Override

Publish to `doorbell/human_active` to preempt AI speech and put the engine into human-handling mode.

```json
{
  "active": true,
  "ttl_s": 120
}
```

Set `active` to `false` to clear the override.

## Home Assistant Integration

### Method 1: Automation (Recommended)

```yaml
# configuration.yaml - Add MQTT
mqtt:
  broker: YOUR_MQTT_IP
  port: 1883

# automations.yaml
- alias: "Doorbell Pressed - Trigger AI Response"
  trigger:
    - platform: state
      entity_id: binary_sensor.front_door_doorbell
      to: "on"
  action:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "{{ state_attr('camera.front_door', 'camera_id') }}",
            "camera_name": "Front Door",
            "source": "home_assistant",
            "context": {
              "trigger_type": "doorbell_press",
              "location": "front_door"
            }
          }
```

### Method 2: Script for Manual Testing

```yaml
# scripts.yaml
trigger_doorbell_ai:
  alias: "Test Doorbell AI"
  sequence:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "your_camera_id",
            "source": "home_assistant_script",
            "context": {
              "trigger_type": "manual_test"
            }
          }
```

### Method 3: Node-RED Flow

```json
[
    {
        "id": "doorbell_trigger",
        "type": "mqtt out",
        "topic": "doorbell/doorbell_press",
        "payload": "{\"camera_id\":\"xyz\",\"source\":\"node_red\"}",
        "broker": "mqtt_broker",
        "name": "Trigger Doorbell AI"
    }
]
```

## Dumb Doorbell Integration

### ESP32/ESP8266 Example

```cpp
#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_PASSWORD";
const char* mqtt_server = "YOUR_MQTT_IP";

WiFiClient espClient;
PubSubClient client(espClient);

const int DOORBELL_PIN = 2;  // Pin connected to doorbell button

void setup() {
  pinMode(DOORBELL_PIN, INPUT_PULLUP);
  
  WiFi.begin(ssid, password);
  client.setServer(mqtt_server, 1883);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  
  // Check if doorbell pressed
  if (digitalRead(DOORBELL_PIN) == LOW) {
    String payload = "{\"camera_id\":\"your_camera_id\",\"source\":\"esp32_doorbell\",\"context\":{\"trigger_type\":\"doorbell_press\"}}";
    client.publish("doorbell/doorbell_press", payload.c_str());
    
    delay(3000);  // Debounce
  }
}

void reconnect() {
  while (!client.connected()) {
    if (client.connect("ESP32DoorbellClient")) {
      // Connected
    } else {
      delay(5000);
    }
  }
}
```

### Raspberry Pi GPIO Example

```python
import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import json
import time

DOORBELL_PIN = 17
MQTT_BROKER = "localhost"
MQTT_TOPIC = "doorbell/doorbell_press"

GPIO.setmode(GPIO.BCM)
GPIO.setup(DOORBELL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

client = mqtt.Client()
client.connect(MQTT_BROKER, 1883, 60)
client.loop_start()

def doorbell_pressed(channel):
    payload = {
        "camera_id": "your_camera_id",
        "camera_name": "Front Door",
        "source": "raspberry_pi_gpio",
        "context": {
            "trigger_type": "doorbell_press",
            "location": "front_door"
        }
    }
    
    client.publish(MQTT_TOPIC, json.dumps(payload))
    print("Doorbell trigger sent!")

GPIO.add_event_detect(DOORBELL_PIN, GPIO.FALLING, 
                     callback=doorbell_pressed, 
                     bouncetime=3000)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    GPIO.cleanup()
    client.disconnect()
```

## Using Web Dashboard

### Camera Selection

1. Open web UI at `http://localhost:8080`
2. View all available cameras from UniFi Protect
3. Click a camera to select it
4. The selected camera will be used for triggers

### Manual Trigger

1. Select a camera
2. Choose trigger source (Home Assistant, Dumb Doorbell, etc.)
3. Set location/zone
4. Add optional JSON context
5. Click "Trigger Doorbell Response"

### Testing Without Hardware

```bash
# Using mosquitto_pub (command line)
mosquitto_pub -h localhost -t "doorbell/doorbell_press" -m '{
  "camera_id": "your_camera_id",
  "source": "test",
  "context": {"trigger_type": "test"}
}'

# Using curl to web UI
curl -X POST http://localhost:8080/api/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "your_camera_id",
    "camera_name": "Test Camera",
    "source": "curl_test"
  }'
```

## Using Any Camera (Not Just G6 Entry)

### Requirements

For a camera to work with the intent engine, it needs:
1. ✅ Two-way audio support (speaker + microphone)
2. ✅ RTSP stream accessible
3. ✅ Listed in UniFi Protect (or compatible API)

### Supported UniFi Cameras

- ✅ G6 Entry (doorbell, recommended)
- ✅ AI Pro (has speaker/mic)
- ✅ G4 Doorbell Pro
- ✅ G3 Instant (if mic enabled)
- ✅ Any UniFi camera with audio I/O

### Non-Doorbell Camera Example

```json
{
  "camera_id": "camera_123",
  "camera_name": "Garage Camera",
  "source": "motion_sensor",
  "context": {
    "trigger_type": "motion_detected",
    "location": "garage_entrance",
    "use_case": "delivery_detection"
  }
}
```

The system will:
1. Use the camera's microphone to listen
2. Process speech with Whisper
3. Generate AI response
4. Play through camera's speaker

## Advanced Configurations

### Time-Based Triggers

```yaml
# Home Assistant: Different behavior based on time
- alias: "Doorbell - Time Aware"
  trigger:
    - platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
  action:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "xyz",
            "source": "home_assistant",
            "context": {
              "time_of_day": "{{ 'night' if now().hour < 7 or now().hour > 21 else 'day' }}",
              "custom_message": "{{ 'Please come back during business hours' if now().hour < 7 or now().hour > 21 else 'default' }}"
            }
          }
```

### Conditional Camera Selection

```yaml
# Use different cameras based on which door
- alias: "Multi-Door Doorbell"
  trigger:
    - platform: state
      entity_id: binary_sensor.front_door_bell
      id: front
    - platform: state
      entity_id: binary_sensor.back_door_bell
      id: back
  action:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "{{ 'front_cam_id' if trigger.id == 'front' else 'back_cam_id' }}",
            "camera_name": "{{ trigger.id | title }} Door",
            "source": "home_assistant",
            "context": {
              "location": "{{ trigger.id }}_door"
            }
          }
```

### Integration with Person Detection

```yaml
# Only trigger if person is detected by camera
- alias: "Smart Doorbell with Person Detection"
  trigger:
    - platform: state
      entity_id: binary_sensor.front_door_person_detected
      to: "on"
  condition:
    - condition: state
      entity_id: binary_sensor.doorbell_pressed
      state: "on"
  action:
    - service: mqtt.publish
      data:
        topic: "doorbell/doorbell_press"
        payload: >
          {
            "camera_id": "xyz",
            "source": "home_assistant_smart",
            "context": {
              "person_detected": true,
              "confidence": "high"
            }
          }
```

## Troubleshooting

### Trigger Not Working

```bash
# Test MQTT connectivity
mosquitto_sub -h YOUR_MQTT_IP -t "doorbell/#" -v

# Check intent engine logs
docker-compose logs -f intent-engine

# Verify MQTT broker
docker-compose logs mqtt
```

### Camera Not Responding

1. Check camera has two-way audio enabled in UniFi Protect
2. Verify camera ID is correct (check web dashboard)
3. Test talkback session creation in logs
4. Ensure network access to camera

### No Audio Output

1. Camera must support speaker output
2. Check UniFi Protect permissions for API token
3. Verify talkback session in logs
4. Test with simple audio file first

## MQTT Topic Reference

### Published by Intent Engine

- `doorbell/status` - System status updates
- `doorbell/intent` - Intent classification output (JSON) for HA/Node-RED automations
- `doorbell/response` - Response sent to visitor (optional)
- `doorbell/event` - Event processing status (optional)

### `doorbell/intent` Payload (Recommended contract)

The intent engine publishes **one stable topic** and uses payload fields to indicate urgency and whether a human should be involved.

```json
{
  "schema_version": 1,
  "timestamp": "2026-01-17T06:18:12.123",
  "source": "frigate",

  "intent": "delivery",
  "confidence": 0.92,
  "entities": {"name":"","company":"FedEx","tracking":"","appointment_time":""},
  "suggested_actions": ["log_event"],
  "response_text": "Great! Please leave it by the door. Thank you!",

  "requires_human": false,
  "priority": "low",
  "handoff_reason": null,
  "human_handoff": {
    "required": false,
    "reason": null,
    "priority": "low",
    "deadline_seconds": null,
    "fallback": null,
    "notify": {"owner": false, "channels": []}
  },
  "notify": {"owner": false, "channels": []},

  "context": {"time_of_day":"morning","has_package":true},
  "transcript": "FedEx, package for Sarah"
}
```

Notes:
- `requires_human` is a convenience mirror of `human_handoff.required` for simpler automations.
- `priority` is one of `low | medium | high`.
- `handoff_reason` is a short string like `signature_required`, `unknown_at_night`, `emergency`, `low_confidence`.
- `transcript` can be disabled via `MQTT_INCLUDE_TRANSCRIPT=false`.

### Subscribed by Intent Engine

- `frigate/events` - Frigate detection events
- `doorbell/doorbell_press` - Manual triggers (configurable)

## Security Considerations

### MQTT Authentication

Add to mosquitto.conf:
```
allow_anonymous false
password_file /mosquitto/config/passwd
```

Create password:
```bash
docker exec doorbell-mqtt mosquitto_passwd -c /mosquitto/config/passwd username
```

### Home Assistant MQTT User

```yaml
# configuration.yaml
mqtt:
  broker: YOUR_MQTT_IP
  port: 1883
  username: doorbell_user
  password: !secret mqtt_password
```

### Network Security

- Use MQTT over TLS for external access
- Keep MQTT broker on internal network
- Use VPN for remote access
- Firewall MQTT port (1883) from internet

## Example Use Cases

### 1. Package Delivery Detection
```json
{
  "camera_id": "front_cam",
  "source": "frigate_package_detection",
  "context": {
    "package_detected": true,
    "person_detected": true,
    "vehicle_type": "delivery_truck"
  }
}
```

### 2. Guest Arrival
```json
{
  "camera_id": "front_cam",
  "source": "calendar_integration",
  "context": {
    "expected_guest": "John Smith",
    "appointment_time": "14:00",
    "custom_greeting": "Welcome! The door will unlock in a moment."
  }
}
```

### 3. After-Hours Response
```json
{
  "camera_id": "office_door",
  "source": "business_hours_automation",
  "context": {
    "business_hours": false,
    "custom_message": "Our office is currently closed. Please call 555-0123 for emergencies."
  }
}
```

## Next Steps

1. Set up Home Assistant automation
2. Test with web dashboard
3. Add your dumb doorbell hardware
4. Configure multiple cameras
5. Customize prompts based on context

For more help, check the main README.md or enable debug logging.

## Repeat-Offender & Face Registration Signals (Optional)

If Frigate face recognition is enabled and a visitor matches a previously trained deterrence label (default prefix `solicitor-`), the intent engine will set:

- `context.recognized_person` : the name Frigate matched (string)
- `context.repeat_offender` : `true` when the name matches the configured prefix
- `human_handoff.reason` may be `repeat_solicitor` and `human_handoff.priority` may be elevated.

### Face Registration Status Events

When `FRIGATE_FACES_ENABLED=true`, the engine may emit best-effort status events on the status topic (`MQTT_STATUS_TOPIC`, default `doorbell/status`) after a solicitor interaction:

```json
{
  "event": "face_registered",
  "timestamp": "2026-01-17T00:00:00Z",
  "event_id": "1234567890.abcdef",
  "face_name": "solicitor-hover_vacuums",
  "label": "Hover Vacuums",
  "intent": "solicitor"
}
```

If registration fails, the engine will log a `face_register_failed` thought event (and otherwise continue normally).
