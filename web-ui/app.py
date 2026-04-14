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
    """Handle MQTT messages"""
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
    """Main dashboard"""
    return render_template('index.html')


@app.route('/api/events')
def get_events():
    """Get recent events"""
    return jsonify({'events': list(recent_events)})


@app.route('/api/status')
def get_status():
    """Get system status"""
    return jsonify({
        'status': 'running',
        'mqtt_connected': mqtt_client.is_connected(),
        'recent_events': len(recent_events)
    })


@app.route('/api/setup/status')
def setup_status():
    return jsonify({'needs_setup': is_first_run()})


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
                current[k] = payload[k]

        if 'mqtt_port' in current:
            current['mqtt_port'] = int(current['mqtt_port'])

        save_runtime(current)
        return jsonify({'ok': True, 'runtime': get_effective_runtime(), 'needs_setup': is_first_run()})
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
