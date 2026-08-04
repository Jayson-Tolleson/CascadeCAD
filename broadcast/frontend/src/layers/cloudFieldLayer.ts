import { samplePatchGrid } from '../fields/sampler';
import type { FieldStore } from '../fields/fieldStore';
import { budgetForTier, type BudgetTier } from '../renderer/budget';
import { ObjectPool } from '../renderer/objectPool';
import { damp, clamp } from '../renderer/interpolation';

interface State { x: number; y: number; opacity: number; scale: number; altitude: number; }

export class CloudFieldLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private readonly state = new Map<string, State>();
  private tier: BudgetTier = 'regional';

  constructor(private readonly fields: FieldStore, parent: HTMLElement) {
    this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object cloud-object' }), budgetForTier('local').clouds, parent);
  }

  setTier(tier: BudgetTier): void { this.tier = tier; }

  tick(deltaSeconds: number): void {
    const samples = samplePatchGrid(this.fields.latestPatch('atmosphere'), budgetForTier(this.tier).clouds);
    const keep = new Set<string>();
    for (const sample of samples) {
      const id = `cloud:${sample.id}`;
      keep.add(id);
      const density = clamp(sample.values.cloud_density ?? 0, 0, 1);
      const windU = sample.values.wind_u ?? 0;
      const windV = sample.values.wind_v ?? 0;
      const target = { x: sample.x * 100 + windU * 0.15, y: (1 - sample.y) * 100 - windV * 0.15, opacity: density * 0.7, scale: 0.6 + density * 1.8, altitude: 1 + density * 8 };
      const current = this.state.get(id) ?? { ...target, opacity: 0, scale: 0.4 };
      current.x = damp(current.x, target.x, deltaSeconds);
      current.y = damp(current.y, target.y, deltaSeconds);
      current.opacity = damp(current.opacity, target.opacity, deltaSeconds);
      current.scale = damp(current.scale, target.scale, deltaSeconds);
      current.altitude = damp(current.altitude, target.altitude, deltaSeconds);
      this.state.set(id, current);
      const node = this.pool.acquire(id);
      if (!node) continue;
      node.className = 'field-object cloud-object';
      node.style.transform = `translate3d(${current.x}vw, ${current.y}vh, 0) scale(${current.scale})`;
      node.style.opacity = current.opacity.toFixed(3);
      node.style.setProperty('--altitude', current.altitude.toFixed(2));
    }
    this.pool.markUnused(keep);
    this.pool.releaseFaded();
  }
}
