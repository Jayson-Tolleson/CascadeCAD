import os

print("[SYS] Initializing CascadeCAD Telemetry Patch Deployment...")

# 1. Create necessary directories if they don't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# 2. Write math_telemetry.py
math_telemetry_code = '''import asyncio
import time
import psutil

class MathTelemetryEngine:
    \"\"\"Backend matrix calculator mapping system state to mathematical telemetry symbols.\"\"\"
    
    def __init__(self, hub):
        self.hub = hub
        self.start_time = time.time()

    def compute_sigma_load(self) -> dict:
        \"\"\"Calculates total system load (Sigma).\"\"\"
        cpu_load = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        return {
            "symbol": "Σ",
            "name": "System Load",
            "cpu": cpu_load,
            "memory": mem,
            "text": f"Σ Load: {cpu_load}% | Mem: {mem}%",
            "level": "math"
        }

    def compute_gamma_mesh(self, vertex_count: int = 14200, face_count: int = 28400) -> dict:
        \"\"\"Calculates active geometry render metrics (Gamma).\"\"\"
        render_ms = round((time.time() % 1) * 16.6, 2)
        return {
            "symbol": "Γ",
            "name": "Mesh Render Matrix",
            "vertices": vertex_count,
            "faces": face_count,
            "frame_ms": render_ms,
            "text": f"Γ Mesh: {vertex_count}v / {face_count}f ({render_ms}ms)",
            "level": "math"
        }

    def compute_phi_interpolation(self) -> dict:
        \"\"\"Calculates UI state transition factor (Phi).\"\"\"
        t = time.time() - self.start_time
        phi = round((t % 10) / 10.0, 3)
        return {
            "symbol": "Φ",
            "name": "State Interpolation",
            "factor": phi,
            "text": f"Φ(t) Interpolation Factor: {phi}",
            "level": "normal"
        }

    async def start_telemetry_loop(self):
        \"\"\"Continuously broadcasts live math telemetry over the WebSocket hub.\"\"\"
        while True:
            try:
                payload = {
                    "type": "debug",
                    "text": f"[MATRIX] {self.compute_sigma_load()['text']} | {self.compute_gamma_mesh()['text']}",
                    "level": "math"
                }
                self.hub.publish("debug", payload)
            except Exception as e:
                print(f"[ERR] Telemetry loop exception: {e}")
            await asyncio.sleep(3.0)
'''

with open("math_telemetry.py", "w") as f:
    f.write(math_telemetry_code)
print("[OK] Created math_telemetry.py")

# 3. Write templates/project.html
project_html_code = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CascadeCAD - HUD Interface</title>
  <style>
    :root {
      --glass-bg: rgba(18, 18, 20, 0.55);
      --glass-border: rgba(255, 255, 255, 0.12);
      --glass-glow: 0 8px 32px 0 rgba(0, 0, 0, 0.6);
      --text-main: #e2e8f0;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --debug-text: #4ade80;
    }

    body, html {
      margin: 0; padding: 0; width: 100vw; height: 100vh;
      background-color: #000;
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: var(--text-main);
      overflow: hidden;
    }

    #pixel-container {
      position: absolute;
      top: 0; left: 0;
      width: 100vw; height: 100vh;
      background: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%);
      z-index: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .glass-panel {
      position: absolute;
      background: var(--glass-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--glass-border);
      box-shadow: var(--glass-glow);
      border-radius: 12px;
      z-index: 10;
      transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .glass-header {
      padding: 10px 16px;
      border-bottom: 1px solid var(--glass-border);
      font-weight: 600;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 1px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      user-select: none;
    }

    #hud-top {
      top: 20px; left: 340px; right: 410px;
      height: 120px;
    }
    #hud-top.minimized {
      transform: translateY(-95px);
      opacity: 0.5;
    }

    #hud-left {
      top: 20px; left: 20px;
      width: 300px; height: calc(100vh - 40px);
    }
    #hud-left.minimized { transform: translateX(calc(-100% + 35px)); opacity: 0.5; }

    #hud-right {
      top: 20px; right: 20px;
      width: 370px; height: calc(100vh - 40px);
    }
    #hud-right.minimized { transform: translateX(calc(100% - 35px)); opacity: 0.5; }

    .hud-section {
      flex: 1;
      border-bottom: 1px solid var(--glass-border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .hud-section:last-child { border-bottom: none; }

    #debug-terminal {
      padding: 10px 12px;
      font-family: 'Fira Code', monospace;
      font-size: 0.72rem;
      color: var(--debug-text);
      overflow-y: auto;
      flex: 1;
      background: rgba(0, 0, 0, 0.3);
    }
    .debug-line { margin-bottom: 3px; }
    .debug-warn { color: #facc15; }
    .debug-err { color: #f87171; }
    .debug-math { color: #c084fc; font-weight: bold; }

    .toggle-zone-side {
      width: 35px; height: 100%;
      position: absolute; top: 0;
      z-index: 5; cursor: pointer;
    }
    #hud-left .toggle-zone-side { right: 0; }
    #hud-right .toggle-zone-side { left: 0; }
  </style>
</head>
<body>

  <div id="pixel-container">
    <h2 style="color: rgba(255,255,255,0.08); font-size: 3rem;">[ RENDER CANVAS ]</h2>
  </div>

  <div id="hud-top" class="glass-panel">
    <div class="glass-header" onclick="togglePanel('hud-top')">
      <span>⚙ Engineering Assistant & API Matrix</span>
      <span>▲ Minimize / Expand</span>
    </div>
    <div style="padding: 12px; font-size: 0.8rem; display: flex; gap: 16px; align-items: center;">
      <div>
        <span class="debug-math">Δ</span> Engine State: <span style="color: var(--accent);">Online</span>
      </div>
      <div>
        <span class="debug-math">Σ</span> API Bindings: <span style="color: var(--accent);">Active</span>
      </div>
      <div style="flex: 1; text-align: right; color: var(--text-muted);">
        System Matrix v2.6.4
      </div>
    </div>
  </div>

  <div id="hud-left" class="glass-panel">
    <div class="toggle-zone-side" onclick="togglePanel('hud-left')"></div>
    <div class="glass-header">
      <span>Assembly & Materials</span>
      <span>≡</span>
    </div>
    <div style="padding: 16px;">
      <p style="font-size: 0.8rem; color: var(--text-muted);">Awaiting geometry nodes...</p>
    </div>
  </div>

  <div id="hud-right" class="glass-panel">
    <div class="toggle-zone-side" onclick="togglePanel('hud-right')"></div>
    <div class="glass-header">
      <span>Telemetry & Collaboration</span>
      <span>≡</span>
    </div>

    <div class="hud-section" style="flex: 0.4;">
      <div style="padding: 10px 12px; font-size: 0.75rem;">
        <div style="display: flex; justify-content: space-between;">
          <span>Φ(t) Interpolation:</span> <span class="debug-math">Nominal</span>
        </div>
      </div>
    </div>

    <div class="hud-section" style="flex: 1.6;">
      <div style="padding: 6px 12px; background: rgba(255,255,255,0.02); border-bottom: 1px solid var(--glass-border); font-size: 0.7rem; color: var(--text-muted);">
        SYSTEM STDOUT / TELEMETRY LOG
      </div>
      <div id="debug-terminal">
        <div class="debug-line">[SYS] Core glass pane initialized.</div>
        <div class="debug-line debug-math">Γ_render loop active at 60fps.</div>
        <div class="debug-line">[WS] Multiplexing telemetry stream...</div>
      </div>
    </div>

    <div class="hud-section" style="flex: 1.2;">
      <div style="padding: 10px 12px; font-size: 0.75rem; color: var(--accent);">[ Channel Chat & Presence ]</div>
      <div style="padding: 0 12px; color: var(--text-muted); font-size: 0.75rem;">Connected to active session.</div>
    </div>
  </div>

  <script src="{{ url_for('static', filename='js/project.js') }}"></script>
</body>
</html>
'''

with open("templates/project.html", "w") as f:
    f.write(project_html_code)
print("[OK] Created templates/project.html")

# 4. Write static/js/project.js
project_js_code = '''function togglePanel(panelId) {
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
'''

with open("static/js/project.js", "w") as f:
    f.write(project_js_code)
print("[OK] Created static/js/project.js")

print("[SUCCESS] All server patch files written successfully.")
