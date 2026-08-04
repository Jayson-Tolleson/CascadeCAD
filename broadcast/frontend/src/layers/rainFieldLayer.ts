import { samplePatchGrid } from '../fields/sampler';
import type { FieldStore } from '../fields/fieldStore';
import { budgetForTier, type BudgetTier } from '../renderer/budget';
import { ObjectPool } from '../renderer/objectPool';
import { clamp, damp } from '../renderer/interpolation';

export class RainFieldLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private tier: BudgetTier = 'regional';

  constructor(private readonly fields: FieldStore, parent: HTMLElement) {
    this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object rain-object' }), budgetForTier('local').rain, parent);
  }

  setTier(tier: BudgetTier): void { this.tier = tier; }

  tick(deltaSeconds: number, now: number): void {
    const samples = samplePatchGrid(this.fields.latestPatch('atmosphere'), budgetForTier(this.tier).rain);
    const keep = new Set<string>();
    for (const sample of samples) {
      const rain = clamp(sample.values.rain_rate ?? 0, 0, 2) / 2;
      if (rain <= 0.02) continue;
      const id = `rain:${sample.id}`;
      keep.add(id);
      const node = this.pool.acquire(id);
      if (!node) continue;
      const phase = ((now / 24 + sample.x * 40) % 16) * rain;
      const currentOpacity = Number(node.style.opacity || 0);
      node.className = 'field-object rain-object';
      node.style.transform = `translate3d(${sample.x * 100}vw, ${(1 - sample.y) * 100 + phase}vh, 0) scale(${0.5 + rain})`;
      node.style.opacity = damp(currentOpacity, 0.25 + rain * 0.65, deltaSeconds, 10).toFixed(3);
      node.style.setProperty('--footprint', `${12 + rain * 36}px`);
    }
    this.pool.markUnused(keep);
    this.pool.releaseFaded();
  }
}
