import type { ReportPoint } from '../types/spatial';
import { budgetForTier, type BudgetTier } from '../renderer/budget';
import { ObjectPool } from '../renderer/objectPool';
import { damp } from '../renderer/interpolation';

export class ReportLayer {
  private readonly pool: ObjectPool<HTMLButtonElement>;
  private reports: ReportPoint[] = [];
  private tier: BudgetTier = 'regional';

  constructor(parent: HTMLElement, private readonly onSelect: (report: ReportPoint) => void) {
    this.pool = new ObjectPool(() => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'field-object report-marker';
      return button;
    }, budgetForTier('local').reports, parent);
  }

  setTier(tier: BudgetTier): void { this.tier = tier; }
  setReports(reports: ReportPoint[]): void { this.reports = reports; }

  tick(deltaSeconds: number): void {
    const keep = new Set<string>();
    for (const report of this.reports.slice(0, budgetForTier(this.tier).reports)) {
      const id = `report:${report.id}`;
      keep.add(id);
      const node = this.pool.acquire(id);
      if (!node) continue;
      node.className = 'field-object report-marker';
      node.title = report.title;
      node.onclick = () => this.onSelect(report);
      const x = ((report.longitude + 87.8) / 14.8) * 100;
      const y = (1 - ((report.latitude - 18.0) / 14.5)) * 100;
      node.style.transform = `translate3d(${x}vw, ${y}vh, 0)`;
      node.style.opacity = damp(Number(node.style.opacity || 0), 0.9, deltaSeconds).toFixed(3);
    }
    this.pool.markUnused(keep);
    this.pool.releaseFaded();
  }
}
