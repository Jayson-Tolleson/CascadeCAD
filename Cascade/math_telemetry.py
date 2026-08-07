import asyncio
import time
import psutil

class MathTelemetryEngine:
    """Backend matrix calculator mapping system state to mathematical telemetry symbols."""
    
    def __init__(self, hub):
        self.hub = hub
        self.start_time = time.time()

    def compute_sigma_load(self) -> dict:
        """Calculates total system load (Sigma)."""
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
        """Calculates active geometry render metrics (Gamma)."""
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
        """Calculates UI state transition factor (Phi)."""
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
        """Continuously broadcasts live math telemetry over the WebSocket hub."""
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
