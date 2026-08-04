import { samplePatchGrid } from '../fields/sampler';
import type { FieldStore } from '../fields/fieldStore';
import { budgetForTier, type BudgetTier } from '../renderer/budget';
import { ObjectPool } from '../renderer/objectPool';
import { clamp, damp } from '../renderer/interpolation';

export class BaitFieldLayer {
  private readonly pool: ObjectPool<HTMLDivElement>;
  private tier: BudgetTier = 'regional';
  constructor(private readonly fields: FieldStore, parent: HTMLElement) { this.pool = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object bait-field-glow' }), budgetForTier('local').bait, parent); }
  setTier(tier: BudgetTier): void { this.tier = tier; }
  tick(deltaSeconds: number): void {
    const samples = samplePatchGrid(this.fields.latestPatch('ocean'), budgetForTier(this.tier).bait);
    const keep = new Set<string>();
    for (const sample of samples) {
      const score = clamp(sample.values.bait_score ?? 0, 0, 1);
      if (score < 0.35) continue;
      const id = `bait-field:${sample.id}`;
      keep.add(id);
      const node = this.pool.acquire(id); if (!node) continue;
      node.className = 'field-object bait-field-glow';
      node.style.transform = `translate3d(${sample.x * 100}vw, ${(1 - sample.y) * 100}vh, 0) scale(${0.7 + score * 2})`;
      node.style.opacity = damp(Number(node.style.opacity || 0), score * 0.8, deltaSeconds).toFixed(3);
    }
    this.pool.markUnused(keep); this.pool.releaseFaded();
  }
}
