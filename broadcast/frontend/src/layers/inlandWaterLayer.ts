import type { SpatialFeature } from '../types/spatial';
import { ObjectPool } from '../renderer/objectPool';
import { damp } from '../renderer/interpolation';

export class InlandWaterLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private waterbodies: SpatialFeature[] = [];
  constructor(parent: HTMLElement) { this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object inland-water-marker' }), 120, parent); }
  setWaterbodies(waterbodies: SpatialFeature[]): void { this.waterbodies = waterbodies; }
  tick(deltaSeconds: number): void {
    const keep = new Set<string>();
    for (const water of this.waterbodies) {
      const id = water.stable_id ?? water.id; keep.add(id);
      const point = water.label_point ?? { lon: water.longitude ?? -120, lat: water.latitude ?? 35 };
      const node = this.pool.acquire(id); if (!node) continue;
      const x = ((point.lon + 125) / 8) * 100; const y = (1 - ((point.lat - 32) / 6)) * 100;
      node.className = 'field-object inland-water-marker'; node.textContent = water.name ?? water.label ?? '';
      node.style.transform = `translate3d(${x}vw, ${y}vh, 0)`;
      node.style.opacity = damp(Number(node.style.opacity || 0), 0.72, deltaSeconds).toFixed(3);
    }
    this.pool.markUnused(keep); this.pool.releaseFaded();
  }
}
