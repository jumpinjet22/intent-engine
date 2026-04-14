let lastTestedConfigKey = null;
let lastTestPassed = false;

function setupPayload() {
  return {
    mqtt_host: document.getElementById('mqtt_host').value.trim(),
    mqtt_port: Number(document.getElementById('mqtt_port').value),
    mqtt_topic: document.getElementById('mqtt_topic').value.trim(),
    frigate_camera: document.getElementById('frigate_camera').value,
    protect_camera_id: document.getElementById('protect_camera_id').value,
    camera_rtsp_url: document.getElementById('camera_rtsp_url').value.trim(),
  };
}

function clearErrors() {
  ['mqtt_host', 'mqtt_port', 'mqtt_topic', 'frigate_camera'].forEach((field) => {
    const node = document.getElementById(`err_${field}`);
    if (node) node.textContent = '';
  });
}

function setStatus(message, ok) {
  const status = document.getElementById('setup-status');
  status.classList.remove('hidden', 'status-ok', 'status-bad');
  status.classList.add(ok ? 'status-ok' : 'status-bad');
  status.textContent = message;
}

function validateForm() {
  clearErrors();
  const body = setupPayload();
  const errors = {};

  if (!body.mqtt_host) errors.mqtt_host = 'MQTT host is required.';
  if (!Number.isInteger(body.mqtt_port) || body.mqtt_port < 1 || body.mqtt_port > 65535) {
    errors.mqtt_port = 'MQTT port must be 1-65535.';
  }
  if (!body.mqtt_topic) errors.mqtt_topic = 'MQTT topic is required.';
  if (!body.frigate_camera) errors.frigate_camera = 'Please select a Frigate camera.';

  Object.entries(errors).forEach(([field, message]) => {
    const node = document.getElementById(`err_${field}`);
    if (node) node.textContent = message;
  });

  return { valid: Object.keys(errors).length === 0, body };
}

function mqttKey(body) {
  return `${body.mqtt_host}:${body.mqtt_port}/${body.mqtt_topic}`;
}

async function loadSetup() {
  const [status, rt, frig, prot] = await Promise.all([
    fetch('/api/setup/status').then((r) => r.json()),
    fetch('/api/runtime').then((r) => r.json()),
    fetch('/api/frigate/cameras').then((r) => r.json()),
    fetch('/api/protect/cameras').then((r) => r.json()),
  ]);

  const runtime = rt.runtime || {};
  const effective = status.effective_mqtt || {};

  const frigSel = document.getElementById('frigate_camera');
  const frigCams = (frig.cameras || []);
  frigSel.innerHTML = frigCams.length
    ? frigCams.map((c) => `<option value="${c}">${c}</option>`).join('')
    : '<option value="">(no cameras found)</option>';
  frigSel.value = runtime.frigate_camera || '';

  const protSel = document.getElementById('protect_camera_id');
  const protCams = (prot.cameras || []);
  protSel.innerHTML = protCams.length
    ? protCams.map((c) => `<option value="${c.id}">${c.name} (${c.id})</option>`).join('')
    : '<option value="">(Protect not configured)</option>';
  protSel.value = runtime.protect_camera_id || '';

  document.getElementById('camera_rtsp_url').value = runtime.camera_rtsp_url || '';
  document.getElementById('mqtt_host').value = runtime.mqtt_host || effective.mqtt_host || '';
  document.getElementById('mqtt_port').value = runtime.mqtt_port || effective.mqtt_port || 1883;
  document.getElementById('mqtt_topic').value = runtime.mqtt_topic || effective.mqtt_topic || '';

  const setupScreen = document.getElementById('setup-screen');
  const main = document.getElementById('main-content');
  if (status.needs_setup) {
    setupScreen.classList.remove('hidden');
    main.classList.add('hidden');
    document.getElementById('setup-reasons').textContent =
      status.reasons && status.reasons.length
        ? `Setup required: ${status.reasons.join('; ')}`
        : 'Setup required.';
  } else {
    setupScreen.classList.add('hidden');
    main.classList.remove('hidden');
  }
}

async function testConnection() {
  const { valid, body } = validateForm();
  if (!valid) {
    setStatus('Fix validation errors before testing connection.', false);
    return;
  }

  const res = await fetch('/api/setup/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const out = await res.json();
  if (out.ok) {
    lastTestedConfigKey = mqttKey(body);
    lastTestPassed = true;
    setStatus(out.message || 'MQTT connection test passed.', true);
  } else {
    lastTestPassed = false;
    setStatus(out.message || 'MQTT connection test failed.', false);
  }
}

async function saveSetup() {
  const { valid, body } = validateForm();
  if (!valid) {
    setStatus('Please fix inline validation errors.', false);
    return;
  }

  if (!lastTestPassed || lastTestedConfigKey !== mqttKey(body)) {
    setStatus('Please run a successful MQTT connection test before finishing setup.', false);
    return;
  }

  const res = await fetch('/api/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  const out = await res.json();
  if (!out.ok) {
    if (out.errors) {
      clearErrors();
      Object.entries(out.errors).forEach(([field, message]) => {
        const node = document.getElementById(`err_${field}`);
        if (node) node.textContent = message;
      });
    }
    setStatus(out.error || 'Failed to save setup.', false);
    return;
  }

  setStatus(out.message || 'Setup saved.', true);
  await loadSetup();
  await refreshEvents();
}

function renderEvents(events) {
  const container = document.getElementById('events');
  if (!events || !events.length) {
    container.innerHTML = '<div class="small">No events yet.</div>';
    return;
  }

  container.innerHTML = events.map((e) => {
    const after = e.after || {};
    const label = after.label || 'unknown';
    const cam = after.camera || 'unknown';
    const zones = (after.current_zones || after.entered_zones || []).join(', ') || 'none';
    const type = e.type || 'event';
    const ts = e.timestamp || '';
    return `
      <div class="event">
        <div class="event-header">
          <div>${type} - ${label}</div>
          <span class="pill">Camera: ${cam}</span>
        </div>
        <div class="event-time">${ts}</div>
        <div>Zones: ${zones}</div>
      </div>
    `;
  }).join('');
}

async function refreshEvents() {
  try {
    const data = await fetch('/api/events').then((r) => r.json());
    renderEvents(data.events || []);
  } catch (e) {
    const container = document.getElementById('events');
    container.innerHTML = '<div class="small">Failed to load events.</div>';
  }
}

window.refreshEvents = refreshEvents;
window.saveSetup = saveSetup;
window.testConnection = testConnection;

window.onload = () => {
  loadSetup();
  refreshEvents();
  setInterval(refreshEvents, 2000);
};
