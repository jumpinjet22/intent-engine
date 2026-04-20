const AppState = {
  lastTestedConfigKey: null,
  lastTestPassed: false,
  eventsRefreshHandle: null,
  statusRefreshHandle: null,
};

const $ = (id) => document.getElementById(id);

const Toasts = {
  container: null,

  init() {
    this.container = $('toast-region');
  },

  show(message, kind = 'ok', timeoutMs = 3200) {
    if (!this.container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${kind}`;
    toast.textContent = message;
    this.container.appendChild(toast);

    window.setTimeout(() => {
      toast.remove();
    }, timeoutMs);
  },
};

const Theme = {
  init() {
    const toggle = $('theme-toggle');
    const persisted = localStorage.getItem('theme');
    if (persisted === 'light' || persisted === 'dark') {
      document.documentElement.dataset.theme = persisted;
    }

    toggle.addEventListener('click', () => {
      const current = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      localStorage.setItem('theme', next);
    });
  },
};

const SetupForm = {
  setupStatus: null,

  init() {
    this.setupStatus = $('setup-status');
    $('test-connection').addEventListener('click', () => this.testConnection());
    $('save-setup').addEventListener('click', () => this.saveSetup());
  },

  payload() {
    return {
      mqtt_host: $('mqtt_host').value.trim(),
      mqtt_port: Number($('mqtt_port').value),
      mqtt_topic: $('mqtt_topic').value.trim(),
      frigate_camera: $('frigate_camera').value,
      protect_camera_id: $('protect_camera_id').value,
      camera_rtsp_url: $('camera_rtsp_url').value.trim(),
      frigate_host: $('frigate_host').value.trim(),
      frigate_port: Number($('frigate_port').value),
      frigate_api_key: $('frigate_api_key').value.trim(),
      protect_base_url: $('protect_base_url').value.trim(),
      protect_api_key: $('protect_api_key').value.trim(),
    };
  },

  mqttKey(body) {
    return `${body.mqtt_host}:${body.mqtt_port}/${body.mqtt_topic}`;
  },

  clearErrors() {
    ['mqtt_host', 'mqtt_port', 'mqtt_topic', 'frigate_camera'].forEach((field) => {
      const node = $(`err_${field}`);
      if (node) node.textContent = '';
    });
  },

  setStatus(message, ok) {
    this.setupStatus.classList.remove('hidden', 'status-ok', 'status-bad');
    this.setupStatus.classList.add(ok ? 'status-ok' : 'status-bad');
    this.setupStatus.textContent = message;
  },

  validate() {
    this.clearErrors();
    const body = this.payload();
    const errors = {};

    if (!body.mqtt_host) errors.mqtt_host = 'MQTT host is required.';
    if (!Number.isInteger(body.mqtt_port) || body.mqtt_port < 1 || body.mqtt_port > 65535) {
      errors.mqtt_port = 'MQTT port must be 1-65535.';
    }
    if (!body.mqtt_topic) errors.mqtt_topic = 'MQTT topic is required.';
    if (!body.frigate_camera) errors.frigate_camera = 'Please select a Frigate camera.';

    Object.entries(errors).forEach(([field, message]) => {
      const node = $(`err_${field}`);
      if (node) node.textContent = message;
    });

    return { valid: Object.keys(errors).length === 0, body };
  },

  async hydrate() {
    const [status, runtimeRes, frigateRes, protectRes] = await Promise.all([
      fetch('/api/setup/status').then((r) => r.json()),
      fetch('/api/runtime').then((r) => r.json()),
      fetch('/api/frigate/cameras').then((r) => r.json()),
      fetch('/api/protect/cameras').then((r) => r.json()),
    ]);

    const runtime = runtimeRes.runtime || {};
    const effective = status.effective_mqtt || {};

    const frigateCameras = frigateRes.cameras || [];
    $('frigate_camera').innerHTML = frigateCameras.length
      ? frigateCameras.map((camera) => `<option value="${camera}">${camera}</option>`).join('')
      : '<option value="">(no cameras found)</option>';

    const protectCameras = protectRes.cameras || [];
    $('protect_camera_id').innerHTML = protectCameras.length
      ? protectCameras.map((camera) => `<option value="${camera.id}">${camera.name} (${camera.id})</option>`).join('')
      : '<option value="">(Protect not configured)</option>';

    $('frigate_camera').value = runtime.frigate_camera || '';
    $('protect_camera_id').value = runtime.protect_camera_id || '';
    $('camera_rtsp_url').value = runtime.camera_rtsp_url || '';
    $('mqtt_host').value = runtime.mqtt_host || effective.mqtt_host || '';
    $('mqtt_port').value = runtime.mqtt_port || effective.mqtt_port || 1883;
    $('mqtt_topic').value = runtime.mqtt_topic || effective.mqtt_topic || '';
    $('frigate_host').value = runtime.frigate_host || '';
    $('frigate_port').value = runtime.frigate_port || 5000;
    $('frigate_api_key').value = runtime.frigate_api_key || '';
    $('protect_base_url').value = runtime.protect_base_url || '';
    $('protect_api_key').value = runtime.protect_api_key || '';

    if (status.needs_setup) {
      $('setup-screen').classList.remove('hidden');
      $('main-content').classList.add('hidden');
      $('setup-reasons').textContent = status.reasons?.length
        ? `Setup required: ${status.reasons.join('; ')}`
        : 'Setup required.';
    } else {
      $('setup-screen').classList.add('hidden');
      $('main-content').classList.remove('hidden');
    }
  },

  async testConnection() {
    const { valid, body } = this.validate();
    if (!valid) {
      this.setStatus('Fix validation errors before testing connection.', false);
      Toasts.show('Validation errors in setup form.', 'error');
      return;
    }

    const response = await fetch('/api/setup/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const result = await response.json();
    if (result.ok) {
      AppState.lastTestedConfigKey = this.mqttKey(body);
      AppState.lastTestPassed = true;
      const message = result.message || 'MQTT connection test passed.';
      this.setStatus(message, true);
      Toasts.show(message, 'ok');
      return;
    }

    AppState.lastTestPassed = false;
    const message = result.message || 'MQTT connection test failed.';
    this.setStatus(message, false);
    Toasts.show(message, 'error');
  },

  async saveSetup() {
    const { valid, body } = this.validate();
    if (!valid) {
      this.setStatus('Please fix inline validation errors.', false);
      Toasts.show('Unable to save setup: fix validation errors.', 'error');
      return;
    }

    if (!AppState.lastTestPassed || AppState.lastTestedConfigKey !== this.mqttKey(body)) {
      const message = 'Please run a successful MQTT connection test before finishing setup.';
      this.setStatus(message, false);
      Toasts.show(message, 'error');
      return;
    }

    const response = await fetch('/api/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const result = await response.json();
    if (!result.ok) {
      if (result.errors) {
        this.clearErrors();
        Object.entries(result.errors).forEach(([field, message]) => {
          const node = $(`err_${field}`);
          if (node) node.textContent = message;
        });
      }

      const message = result.error || 'Failed to save setup.';
      this.setStatus(message, false);
      Toasts.show(message, 'error');
      return;
    }

    const message = result.message || 'Setup saved.';
    this.setStatus(message, true);
    Toasts.show(message, 'ok');
    await this.hydrate();
    await EventsPanel.refresh();
    await StatusCards.refresh();
  },
};

const EventsPanel = {
  container: null,

  init() {
    this.container = $('events');
    $('refresh-events').addEventListener('click', () => this.refresh());
  },

  render(events) {
    if (!events?.length) {
      this.container.innerHTML = '<div class="small">No events yet.</div>';
      return;
    }

    this.container.innerHTML = events.map((event) => {
      const after = event.after || {};
      const label = after.label || 'unknown';
      const camera = after.camera || 'unknown';
      const zones = (after.current_zones || after.entered_zones || []).join(', ') || 'none';
      return `
        <article class="event">
          <div class="event-header">
            <div>${event.type || 'event'} - ${label}</div>
            <span class="pill">Camera: ${camera}</span>
          </div>
          <div class="event-time">${event.timestamp || ''}</div>
          <div>Zones: ${zones}</div>
        </article>
      `;
    }).join('');
  },

  async refresh() {
    try {
      const data = await fetch('/api/events').then((res) => res.json());
      this.render(data.events || []);
    } catch {
      this.container.innerHTML = '<div class="small">Failed to load events.</div>';
      Toasts.show('Could not fetch events from /api/events.', 'error');
    }
  },
};

const StatusCards = {
  container: null,
  lastRefresh: null,

  init() {
    this.container = $('status-cards');
    this.render({
      status: 'starting',
      mqtt_connection_state: 'unknown',
      recent_events: '-',
      mqtt_config: {},
    });
  },

  render(status) {
    const cards = [
      { label: 'Service', value: status.status || 'unknown' },
      { label: 'MQTT', value: status.mqtt_connection_state || (status.mqtt_connected ? 'connected' : 'disconnected') },
      { label: 'Topic', value: status.mqtt_config?.mqtt_topic || 'n/a' },
      { label: 'Recent events', value: `${status.recent_events ?? 0}` },
    ];

    this.container.innerHTML = cards.map((card) => `
      <article class="health-card">
        <div class="health-label">${card.label}</div>
        <div class="health-value">${card.value}</div>
      </article>
    `).join('');
  },

  async refresh() {
    try {
      const status = await fetch('/api/status').then((res) => res.json());
      this.render(status);
      this.lastRefresh = new Date();
    } catch {
      Toasts.show('Status refresh failed from /api/status.', 'error');
    }
  },
};

async function boot() {
  Toasts.init();
  Theme.init();
  SetupForm.init();
  EventsPanel.init();
  StatusCards.init();

  await SetupForm.hydrate();
  await Promise.all([EventsPanel.refresh(), StatusCards.refresh()]);

  AppState.eventsRefreshHandle = window.setInterval(() => EventsPanel.refresh(), 2000);
  AppState.statusRefreshHandle = window.setInterval(() => StatusCards.refresh(), 5000);
}

window.addEventListener('load', () => {
  boot();
});
