function togglePanel(panelId) {
  const panel = document.getElementById(panelId);
  panel.classList.toggle('minimized');
  logDebug(`[UI] Matrix shift: ${panelId} toggled.`, 'math');
}

function logDebug(msg, type = 'normal') {
  const term = document.getElementById('debug-terminal');
  const div = document.createElement('div');
  div.className = `debug-line ${type === 'math' ? 'debug-math' : ''} ${type === 'warn' ? 'debug-warn' : ''} ${type === 'err' ? 'debug-err' : ''}`;
  div.innerText = msg;
  term.appendChild(div);
  term.scrollTop = term.scrollHeight;
}

function initDebugTelemetry() {
  const token = localStorage.getItem('cascade_cad_token') || 'default_token';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const debugWsUrl = `${proto}//${window.location.host}/ws/collaboration?token=${token}&channel=debug`;

  const debugSocket = new WebSocket(debugWsUrl);

  debugSocket.onopen = () => {
    logDebug("[SYS] Telemetry stream online. Listening to backend matrices...", "math");
  };

  debugSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "debug") {
        logDebug(data.text, data.level);
      }
    } catch (err) {
      console.error("Failed to parse telemetry frame:", err);
    }
  };

  debugSocket.onclose = () => {
    logDebug("[WARN] Telemetry stream disconnected. Reconnecting in 3s...", "warn");
    setTimeout(initDebugTelemetry, 3000);
  };

  debugSocket.onerror = (err) => {
    logDebug("[ERR] Telemetry socket failure.", "err");
  };
}

window.addEventListener('DOMContentLoaded', () => {
  initDebugTelemetry();
});
