type WakeLockSentinelLike = WakeLockSentinel;

export class BroadcastWakeLock {
  private sentinel?: WakeLockSentinelLike;
  private enabled = false;
  private keepAliveTimer?: number;

  constructor(private readonly status: (line: string, active: boolean) => void) {
    document.addEventListener('visibilitychange', () => {
      if (this.enabled && document.visibilityState === 'visible') void this.acquire();
    });
    window.addEventListener('pagehide', () => void this.release());
  }

  async start() {
    this.enabled = true;
    this.startKeepAlivePulse();
    await this.acquire();
  }

  private async acquire() {
    if (!this.enabled) return;
    if (!('wakeLock' in navigator) || !navigator.wakeLock) {
      this.status('Wake lock: fallback keepalive', false);
      return;
    }
    try {
      this.sentinel = await navigator.wakeLock.request('screen');
      this.sentinel.addEventListener('release', () => {
        this.status('Wake lock: released; will reacquire', false);
        if (this.enabled && document.visibilityState === 'visible') setTimeout(() => void this.acquire(), 750);
      });
      this.status('Wake lock: active', true);
    } catch (error) {
      const name = error instanceof Error ? error.name : 'blocked';
      this.status(`Wake lock: ${name}; fallback keepalive`, false);
    }
  }

  private startKeepAlivePulse() {
    if (this.keepAliveTimer) return;
    this.keepAliveTimer = window.setInterval(() => {
      const video = document.querySelector<HTMLVideoElement>('#preview');
      if (video && video.paused && video.srcObject) void video.play().catch(() => undefined);
    }, 20_000);
  }

  async release() {
    this.enabled = false;
    if (this.keepAliveTimer) window.clearInterval(this.keepAliveTimer);
    this.keepAliveTimer = undefined;
    const current = this.sentinel;
    this.sentinel = undefined;
    if (current && !current.released) await current.release().catch(() => undefined);
    this.status('Wake lock: off', false);
  }
}
