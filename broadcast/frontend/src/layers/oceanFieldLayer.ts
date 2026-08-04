import { samplePatchGrid } from '../fields/sampler';
import type { FieldStore } from '../fields/fieldStore';
import { budgetForTier, type BudgetTier } from '../renderer/budget';
import { ObjectPool } from '../renderer/objectPool';
import { clamp, damp } from '../renderer/interpolation';

export class OceanFieldLayer {
  private readonly streamlets: ObjectPool<HTMLDivElement>;
  private readonly baitGlows: ObjectPool<HTMLDivElement>;
  private tier: BudgetTier = 'regional';

  constructor(private readonly fields: FieldStore, parent: HTMLElement) {
    this.streamlets = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object ocean-streamlet' }), budgetForTier('local').ocean, parent);
    this.baitGlows = new ObjectPool(() => Object.assign(document.createElement('div'), { className: 'field-object bait-glow' }), budgetForTier('local').ocean, parent);
  }

  setTier(tier: BudgetTier): void { this.tier = tier; }

  tick(deltaSeconds: number): void {
    const samples = samplePatchGrid(this.fields.latestPatch('ocean'), budgetForTier(this.tier).ocean);
    const keepStream = new Set<string>();
    const keepBait = new Set<string>();
    for (const sample of samples) {
      const u = sample.values.current_u ?? 0;
      const v = sample.values.current_v ?? 0;
      const sst = sample.values.sst_c ?? 20;
      const bait = clamp(sample.values.bait_score ?? 0, 0, 1);
      const streamId = `current:${sample.id}`;
      keepStream.add(streamId);
      const stream = this.streamlets.acquire(streamId);
      if (stream) {
        const opacity = damp(Number(stream.style.opacity || 0), 0.25 + clamp(Math.abs(u) + Math.abs(v), 0, 2) * 0.25, deltaSeconds);
        stream.className = 'field-object ocean-streamlet';
        stream.style.transform = `translate3d(${sample.x * 100}vw, ${(1 - sample.y) * 100}vh, 0) rotate(${Math.atan2(v, u) || 0}rad) scaleX(${1 + sst / 30})`;
        stream.style.opacity = opacity.toFixed(3);
      }
      if (bait > 0.3) {
        const baitId = `bait:${sample.id}`;
        keepBait.add(baitId);
        const glow = this.baitGlows.acquire(baitId);
        if (glow) {
          glow.className = 'field-object bait-glow';
          glow.style.transform = `translate3d(${sample.x * 100}vw, ${(1 - sample.y) * 100}vh, 0) scale(${0.7 + bait * 1.8})`;
          glow.style.opacity = damp(Number(glow.style.opacity || 0), bait * 0.75, deltaSeconds).toFixed(3);
        }
      }
    }
    this.streamlets.markUnused(keepStream);
    this.baitGlows.markUnused(keepBait);
    this.streamlets.releaseFaded();
    this.baitGlows.releaseFaded();
  }
}
