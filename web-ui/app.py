"""Simple web UI for monitoring doorbell events + runtime setup.

Infra stays in env vars (hosts/keys). The UI saves user-editable setup values
to /data/runtime.json so you don't have to redeploy to change settings.
"""

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import paho.mqtt.client as mqtt
import json
import os
from pathlib import Path
from datetime import datetime
from collections import deque
import threading
import requests

app = Flask(__name__)
CORS(app)

# Store recent events
recent_events = deque(maxlen=50)

# Runtime config path (shared volume with intent-engine)
RUNTIME_CONFIG_PATH = os.getenv('RUNTIME_CONFIG_PATH', '/data/runtime.json')

# Defaults from env/.env (runtime.json overrides these for user-editable fields)
EDITABLE_DEFAULTS = {
    'mqtt_host': os.getenv('MQTT_HOST', 'localhost'),
    'mqtt_port': int(os.getenv('MQTT_PORT', '1883')),
    'frigate_camera': os.getenv('FRIGATE_CAMERA', ''),
    'protect_camera_id': os.getenv('PROTECT_CAMERA_ID', ''),
    'camera_rtsp_url': os.getenv('CAMERA_RTSP_URL', ''),
}

RUNTIME_EDITABLE_FIELDS = set(EDITABLE_DEFAULTS.keys())
REQUIRED_RUNTIME_KEYS = {'mqtt_host', 'mqtt_port', 'frigate_camera'}

# MQTT topic remains infra-level env configuration
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'frigate/events')

# Frigate / Protect infra credentials and hosts
FRIGATE_HOST = os.getenv('FRIGATE_HOST', 'frigate')
FRIGATE_PORT = int(os.getenv('FRIGATE_PORT', '5000'))
FRIGATE_API_KEY = os.getenv('FRIGATE_API_KEY', '')

PROTECT_BASE_URL = os.getenv('PROTECT_BASE_URL', '')
PROTECT_API_KEY = os.getenv('PROTECT_API_KEY', '')
PROTECT_VERIFY_SSL = os.getenv('PROTECT_VERIFY_SSL', 'false').lower() == 'true'

mqtt_client = None
mqtt_lock = threading.Lock()
active_mqtt_config = {
    'mqtt_host': MQTT_HOST,
    'mqtt_port': MQTT_PORT,
    'mqtt_topic': MQTT_TOPIC,
}


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


def get_effective_runtime() -> dict:
    """Merge order: env defaults first, runtime.json overrides for editable fields."""
    effective = dict(EDITABLE_DEFAULTS)
    runtime = load_runtime()

    for key in RUNTIME_EDITABLE_FIELDS:
        if key in runtime:
            effective[key] = runtime[key]

    return effective


def is_first_run() -> bool:
    """True when runtime.json is missing required setup keys/values."""
    runtime = load_runtime()

    for key in REQUIRED_RUNTIME_KEYS:
        if key not in runtime:
            return True

    if not str(runtime.get('mqtt_host', '')).strip():
        return True

    try:
        port = int(runtime.get('mqtt_port'))
        if port <= 0:
            return True
    except Exception:
        return True

    if not str(runtime.get('frigate_camera', '')).strip():
        return True

    return False


mqtt_client = mqtt.Client()


def on_mqtt_message(client, userdata, msg):
    """Handle MQTT messages."""
    try:
        event = json.loads(msg.payload.decode())
        event['timestamp'] = datetime.now().isoformat()
        recent_events.append(event)
    except Exception:
        pass


mqtt_client.on_message = on_mqtt_message
_effective_runtime = get_effective_runtime()
mqtt_client.connect(_effective_runtime['mqtt_host'], int(_effective_runtime['mqtt_port']), 60)
mqtt_client.subscribe(MQTT_TOPIC)
mqtt_client.loop_start()


@app.route('/')
def index():
    """Main dashboard."""
    return render_template('index.html')


@app.route('/api/events')
def get_events():
    """Get recent events"""
    return jsonify({'events': list(recent_events)})



@app.route('/api/status')
def get_status():
    """Get system status."""
    client = mqtt_client
    return jsonify({
        'status': 'running',
        'mqtt_connected': mqtt_client.is_connected(),
        'mqtt_connection_state': mqtt_connection_state,
        'mqtt_config': current_mqtt_config,
        'recent_events': len(recent_events)
    })


@app.route('/api/setup/status')
def get_setup_status():
    runtime = load_runtime()
    needs_setup, reasons = setup_needed(runtime)
    return jsonify({
        'needs_setup': needs_setup,
        'reasons': reasons,
        'runtime': runtime,
        'effective_mqtt': normalize_mqtt_config(runtime),
    })


@app.route('/api/setup/test', methods=['POST'])
def test_setup_connection():
    payload = request.get_json(force=True) or {}
    errors = validate_setup_payload(payload, require_camera=False)
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    test_client = mqtt.Client()
    try:
        test_client.connect(payload['mqtt_host'].strip(), int(payload['mqtt_port']), 10)
        test_client.disconnect()
        return jsonify({'ok': True, 'message': 'Connected to MQTT broker successfully.'})
    except Exception as exc:
        return jsonify({'ok': False, 'message': f'Connection failed: {exc}'}), 400


@app.route('/api/runtime', methods=['GET', 'POST'])
def runtime_config():
    if request.method == 'GET':
        return jsonify({'runtime': get_effective_runtime(), 'needs_setup': is_first_run()})

    try:
        payload = request.get_json(force=True) or {}
        current = load_runtime()

        # Whitelist fields the UI is allowed to change (runtime source of truth)
        for k in RUNTIME_EDITABLE_FIELDS:
            if k in payload:
                if current.get(k) != payload[k] and k in {'mqtt_host', 'mqtt_port', 'mqtt_topic'}:
                    changed_mqtt = True
                current[k] = payload[k]

        if 'mqtt_port' in current:
            current['mqtt_port'] = int(current['mqtt_port'])

        save_runtime(current)
        mqtt_error = None
        if any(k in payload for k in ['mqtt_host', 'mqtt_port', 'mqtt_topic']):
            _, mqtt_error = reconnect_mqtt_client(current)

        return jsonify({'ok': mqtt_error is None, 'runtime': current, 'mqtt_error': mqtt_error})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@app.route('/api/setup', methods=['POST'])
def setup_config():
    payload = request.get_json(force=True) or {}
    errors = validate_setup_payload(payload, require_camera=True)
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400

    current = load_runtime()
    for key in [
        'mqtt_host',
        'mqtt_port',
        'mqtt_topic',
        'frigate_camera',
        'protect_camera_id',
        'camera_rtsp_url',
    ]:
        if key in payload:
            current[key] = payload[key]

    save_runtime(current)
    ok, error = reconnect_mqtt_client(current)
    if not ok:
        return jsonify({'ok': False, 'error': f'Saved setup, but MQTT reconnect failed: {error}'}), 502

    return jsonify({'ok': True, 'runtime': current, 'message': 'Setup saved and MQTT reconnected.'})


@app.route('/api/frigate/cameras')
def frigate_cameras():
    try:
        headers = {}
        if FRIGATE_API_KEY:
            headers['Authorization'] = f'Bearer {FRIGATE_API_KEY}'
        url = f"http://{FRIGATE_HOST}:{FRIGATE_PORT}/api/config"
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return jsonify({'cameras': []})
        cfg = response.json() if response.content else {}
        cams = sorted((cfg.get('cameras') or {}).keys())
        return jsonify({'cameras': cams})
    except Exception:
        return jsonify({'cameras': []})


@app.route('/api/protect/cameras')
def protect_cameras():
    if not PROTECT_BASE_URL or not PROTECT_API_KEY:
        return jsonify({'cameras': []})
    try:
        session = requests.Session()
        session.headers.update({'Authorization': f'Bearer {PROTECT_API_KEY}'})
        response = session.get(PROTECT_BASE_URL.rstrip('/') + '/cameras', verify=PROTECT_VERIFY_SSL, timeout=8)
        if response.status_code != 200:
            return jsonify({'cameras': []})
        items = response.json() if response.content else []
        cams = []
        for camera in items if isinstance(items, list) else []:
            cams.append({'id': camera.get('id', ''), 'name': camera.get('name', camera.get('type', 'camera'))})
        cams = [camera for camera in cams if camera.get('id')]
        return jsonify({'cameras': cams})
    except Exception:
        return jsonify({'cameras': []})


if __name__ == '__main__':
    reconnect_mqtt_client()
    app.run(host='0.0.0.0', port=8080, debug=False)
