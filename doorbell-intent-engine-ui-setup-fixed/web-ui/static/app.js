async function loadSetup() {
  const rt = await fetch('/api/runtime').then(r => r.json());
  const frig = await fetch('/api/frigate/cameras').then(r => r.json());
  const prot = await fetch('/api/protect/cameras').then(r => r.json());

  const frigSel = document.getElementById('frigate_camera');
  const frigCams = (frig.cameras || []);
  frigSel.innerHTML = frigCams.length
    ? frigCams.map(c => `<option value="${c}">${c}</option>`).join('')
    : `<option value="">(no cameras found)</option>`;
  frigSel.value = (rt.runtime && rt.runtime.frigate_camera) ? rt.runtime.frigate_camera : '';

  const protSel = document.getElementById('protect_camera_id');
  const protCams = (prot.cameras || []);
  protSel.innerHTML = protCams.length
    ? protCams.map(c => `<option value="${c.id}">${c.name} (${c.id})</option>`).join('')
    : `<option value="">(Protect not configured)</option>`;
  protSel.value = (rt.runtime && rt.runtime.protect_camera_id) ? rt.runtime.protect_camera_id : '';

  const rtsp = document.getElementById('camera_rtsp_url');
  rtsp.value = (rt.runtime && rt.runtime.camera_rtsp_url) ? rt.runtime.camera_rtsp_url : '';
}

async function saveSetup() {
  const body = {
    frigate_camera: document.getElementById('frigate_camera').value,
    protect_camera_id: document.getElementById('protect_camera_id').value,
    camera_rtsp_url: document.getElementById('camera_rtsp_url').value,
  };

  const res = await fetch('/api/runtime', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  const out = await res.json();
  if (out.ok) {
    alert('Saved! Intent engine will use the selected camera(s).');
  } else {
    alert('Save failed: ' + (out.error || 'unknown'));
  }
}

function renderEvents(events) {
  const container = document.getElementById('events');
  if (!events || !events.length) {
    container.innerHTML = '<div class="small">No events yet.</div>';
    return;
  }

  container.innerHTML = events.map(e => {
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
    const data = await fetch('/api/events').then(r => r.json());
    renderEvents(data.events || []);
  } catch (e) {
    const container = document.getElementById('events');
    container.innerHTML = '<div class="small">Failed to load events.</div>';
  }
}

window.refreshEvents = refreshEvents;
window.saveSetup = saveSetup;

window.onload = () => {
  refreshEvents();
  loadSetup();
  setInterval(refreshEvents, 2000);
};
