import type { LightningFlash } from '../types/layers';
import { ObjectPool } from '../renderer/objectPool';

export class LightningLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private flashes = new Map<string, LightningFlash>();
  constructor(parent: HTMLElement) { this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object lightning-flash' }), 50, parent); }
  addFlashes(flashes: LightningFlash[]): void { for (const flash of flashes) this.flashes.set(flash.id, flash); }
  tick(_: number, now: number): void {
    const keep = new Set<string>();
    for (const [id, flash] of Array.from(this.flashes)) {
      const age = (now - Date.parse(flash.created_at)) / 1000;
      if (age > flash.ttl_seconds) { this.flashes.delete(id); continue; }
      keep.add(id);
      const node = this.pool.acquire(id); if (!node) continue;
      const x = ((flash.lon + 125) / 8) * 100;
      const y = (1 - ((flash.lat - 32) / 6)) * 100;
      node.className = 'field-object lightning-flash';
      node.style.transform = `translate3d(${x}vw, ${y}vh, 0) scale(${0.8 + flash.energy})`;
      node.style.opacity = Math.max(0, 1 - age / flash.ttl_seconds).toFixed(3);
    }
    this.pool.markUnused(keep); this.pool.releaseFaded();
  }
}
