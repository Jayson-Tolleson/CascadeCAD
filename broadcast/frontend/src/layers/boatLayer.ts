import type { BoatEntity } from '../types/layers';
import { ObjectPool } from '../renderer/objectPool';
import { damp } from '../renderer/interpolation';

export class BoatLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private boats: BoatEntity[] = [];
  constructor(parent: HTMLElement) { this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object boat-marker' }), 32, parent); }
  setBoats(boats: BoatEntity[]): void { this.boats = boats; }
  tick(deltaSeconds: number): void {
    const keep = new Set<string>();
    for (const boat of this.boats) {
      keep.add(boat.id);
      const node = this.pool.acquire(boat.id); if (!node) continue;
      const x = ((boat.lon + 125) / 8) * 100;
      const y = (1 - ((boat.lat - 32) / 6)) * 100;
      node.className = 'field-object boat-marker';
      node.style.transform = `translate3d(${x}vw, ${y}vh, 0) rotate(${boat.heading_deg}deg)`;
      node.style.opacity = damp(Number(node.style.opacity || 0), 0.9, deltaSeconds).toFixed(3);
      node.title = `${boat.id} ${boat.safety}`;
    }
    this.pool.markUnused(keep); this.pool.releaseFaded();
  }
}
