"""Simple web UI for monitoring doorbell events + runtime setup.

Infra stays in env vars (hosts/keys). The UI saves camera selection (and optional RTSP URL)
to /data/runtime.json so you don't have to redeploy to switch cameras.
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import paho.mqtt.client as mqtt
import json
import os
from pathlib import Path
from datetime import datetime
from collections import deque
import requests

app = Flask(__name__)
CORS(app)

# Store recent events
recent_events = deque(maxlen=50)

# Runtime config path (shared volume with intent-engine)
RUNTIME_CONFIG_PATH = os.getenv('RUNTIME_CONFIG_PATH', '/data/runtime.json')

# MQTT configuration defaults
MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'frigate/events')

# Frigate / Protect (hosts/keys in env; UI chooses camera)
FRIGATE_HOST = os.getenv('FRIGATE_HOST', 'frigate')
FRIGATE_PORT = int(os.getenv('FRIGATE_PORT', '5000'))
FRIGATE_API_KEY = os.getenv('FRIGATE_API_KEY', '')

PROTECT_BASE_URL = os.getenv('PROTECT_BASE_URL', '')
PROTECT_API_KEY = os.getenv('PROTECT_API_KEY', '')
PROTECT_VERIFY_SSL = os.getenv('PROTECT_VERIFY_SSL', 'false').lower() == 'true'


def load_runtime() -> dict:
    try:
        p = Path(RUNTIME_CONFIG_PATH)
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding='utf-8') or '{}')
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime(data: dict) -> None:
    p = Path(RUNTIME_CONFIG_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def mqtt_config_from_runtime(runtime: dict | None = None) -> dict:
    rt = runtime if isinstance(runtime, dict) else load_runtime()
    return {
        'host': rt.get('mqtt_host', MQTT_HOST),
        'port': int(rt.get('mqtt_port', MQTT_PORT)),
        'topic': rt.get('mqtt_topic', MQTT_TOPIC),
    }


def on_mqtt_message(client, userdata, msg):
    """Handle MQTT messages."""
    try:
        event = json.loads(msg.payload.decode())
        event['timestamp'] = datetime.now().isoformat()
        recent_events.append(event)
    except Exception:
        pass


def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connection_state
    if reason_code == 0:
        mqtt_connection_state = 'connected'
        client.subscribe(current_mqtt_config['topic'])
    else:
        mqtt_connection_state = f'connect_failed:{reason_code}'


def on_mqtt_disconnect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connection_state
    if reason_code == 0:
        mqtt_connection_state = 'disconnected'
    else:
        mqtt_connection_state = f'disconnected:{reason_code}'


def build_mqtt_client(config):
    client = mqtt.Client()
    client.on_message = on_mqtt_message
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    return client


def connect_mqtt():
    global mqtt_connection_state
    mqtt_connection_state = 'connecting'
    mqtt_client.connect(current_mqtt_config['host'], current_mqtt_config['port'], 60)
    mqtt_client.loop_start()


def reconnect_mqtt(new_config):
    global mqtt_client, current_mqtt_config, mqtt_connection_state

    mqtt_connection_state = 'reconnecting'

    try:
        mqtt_client.loop_stop()
    except Exception:
        pass

    try:
        mqtt_client.disconnect()
    except Exception:
        pass

    current_mqtt_config = {
        'host': new_config['host'],
        'port': int(new_config['port']),
        'topic': new_config['topic'],
    }

    mqtt_client = build_mqtt_client(current_mqtt_config)
    connect_mqtt()


current_mqtt_config = mqtt_config_from_runtime()
mqtt_connection_state = 'initialized'
mqtt_client = build_mqtt_client(current_mqtt_config)
connect_mqtt()


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/api/events')
def get_events():
    """Get recent events"""
    return jsonify({
        'events': list(recent_events)
    })


@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        'status': 'running',
        'mqtt_connected': mqtt_client.is_connected(),
        'mqtt_connection_state': mqtt_connection_state,
        'mqtt_config': current_mqtt_config,
        'recent_events': len(recent_events)
    })


@app.route('/api/runtime', methods=['GET', 'POST'])
def runtime_config():
    if request.method == 'GET':
        return jsonify({'runtime': load_runtime()})

    try:
        payload = request.get_json(force=True) or {}
        current = load_runtime()

        # Whitelist fields the UI is allowed to change
        changed_mqtt = False
        for k in ['frigate_camera', 'protect_camera_id', 'camera_rtsp_url', 'mqtt_host', 'mqtt_port', 'mqtt_topic']:
            if k in payload:
                if current.get(k) != payload[k] and k in {'mqtt_host', 'mqtt_port', 'mqtt_topic'}:
                    changed_mqtt = True
                current[k] = payload[k]

        save_runtime(current)

        if changed_mqtt:
            reconnect_mqtt(mqtt_config_from_runtime(current))

        return jsonify({'ok': True, 'runtime': current, 'mqtt_reconnected': changed_mqtt})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/frigate/cameras')
def frigate_cameras():
    try:
        headers = {}
        if FRIGATE_API_KEY:
            headers['Authorization'] = f'Bearer {FRIGATE_API_KEY}'
        url = f"http://{FRIGATE_HOST}:{FRIGATE_PORT}/api/config"
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            return jsonify({'cameras': []})
        cfg = r.json() if r.content else {}
        cams = sorted((cfg.get('cameras') or {}).keys())
        return jsonify({'cameras': cams})
    except Exception:
        return jsonify({'cameras': []})


@app.route('/api/protect/cameras')
def protect_cameras():
    if not PROTECT_BASE_URL or not PROTECT_API_KEY:
        return jsonify({'cameras': []})
    try:
        s = requests.Session()
        s.headers.update({'Authorization': f'Bearer {PROTECT_API_KEY}'})
        r = s.get(PROTECT_BASE_URL.rstrip('/') + '/cameras', verify=PROTECT_VERIFY_SSL, timeout=8)
        if r.status_code != 200:
            return jsonify({'cameras': []})
        items = r.json() if r.content else []
        cams = []
        for c in items if isinstance(items, list) else []:
            cams.append({'id': c.get('id', ''), 'name': c.get('name', c.get('type', 'camera'))})
        cams = [c for c in cams if c.get('id')]
        return jsonify({'cameras': cams})
    except Exception:
        return jsonify({'cameras': []})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
