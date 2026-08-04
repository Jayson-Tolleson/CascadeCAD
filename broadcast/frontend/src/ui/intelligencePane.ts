import type { ReportPoint, SpatialFeature } from '../types/spatial';
import type { FieldStreamEvent } from '../types/stream';

export interface SharkIntelSelection {
  title: string;
  lat: number;
  lon: number;
  score: number;
  source: string;
  summary: string;
  evidence: Array<[string, string]>;
}

export interface LocationMetric {
  label: string;
  value: string;
  detail?: string;
  tone?: 'good' | 'warn' | 'hot' | 'cold' | 'neutral';
}

export interface LocationIntelContext {
  bboxLabel?: string;
  spatialSource?: string;
  postgisMode?: string;
  nearestWater?: SpatialFeature | null;
  nearestHarbor?: SpatialFeature | null;
  ocean?: {
    source?: string;
    sampleId?: string;
    distanceKm?: number;
    baitScore?: number;
    currentSpeed?: number;
    currentDirection?: string;
    currentVector?: string;
    depthM?: number;
    scalarZ?: number;
    tempC?: number;
    tempF?: number;
  } | null;
  atmosphere?: {
    source?: string;
    sampleId?: string;
    distanceKm?: number;
    cloudPct?: number;
    cloudFamily?: string;
    rainIntensity?: number;
    windSpeed?: number;
    windDirection?: string;
    humidityPct?: number;
    validTime?: string;
  } | null;
  counts?: {
    locations?: number;
    waterbodies?: number;
    harbors?: number;
  };
}

function escapeHtml(value: string): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function isUseful(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0 && value.trim().toLowerCase() !== 'none';
}

function niceKey(key: string): string {
  return key
    .replace(/^report_(\d+)$/i, 'Report $1')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function reportEntries(report: ReportPoint): Array<[string, string]> {
  const fields = report.csv_fields ?? {};
  const ordered = ['name', 'location', 'title', 'lat', 'lon', 'observed_at', 'summary', ...(report.report_indices ?? [])];
  const seen = new Set<string>();
  const entries: Array<[string, string]> = [];
  for (const key of ordered) {
    const value = fields[key] ?? (key === 'title' ? report.title : key === 'summary' ? report.summary : '');
    if (!isUseful(value) || seen.has(key)) continue;
    seen.add(key);
    entries.push([key, value.trim()]);
  }
  for (const [key, value] of Object.entries(fields)) {
    if (!isUseful(value) || seen.has(key)) continue;
    seen.add(key);
    entries.push([key, value.trim()]);
  }
  if (!seen.has('lat')) entries.unshift(['lat', report.latitude.toFixed(5)]);
  if (!seen.has('lon')) entries.splice(1, 0, ['lon', report.longitude.toFixed(5)]);
  if (isUseful(report.observed_at) && !seen.has('observed_at')) entries.push(['observed_at', report.observed_at]);
  if (isUseful(report.summary) && !seen.has('summary')) entries.push(['summary', report.summary]);
  if (!entries.length) entries.push(['summary', report.summary || 'CSV location']);
  return entries;
}

function timelineEntries(report: ReportPoint): Array<[string, string]> {
  const fields = report.csv_fields ?? {};
  const keys = (report.report_indices ?? [])
    .filter((key) => isUseful(fields[key]))
    .sort((a, b) => {
      const na = Number(a.split('_')[1] ?? 9999);
      const nb = Number(b.split('_')[1] ?? 9999);
      return na - nb;
    });
  if (keys.length) return keys.map((key) => [niceKey(key), fields[key].trim()]);
  return isUseful(report.summary) ? [['Summary', report.summary]] : [];
}

function scoreFromReport(report: ReportPoint, context?: LocationIntelContext): number {
  const reportCount = timelineEntries(report).length;
  const text = `${report.title} ${report.summary} ${Object.values(report.csv_fields ?? {}).join(' ')}`.toLowerCase();
  const catchWords = ['caught', 'hookup', 'bite', 'bites', 'fish', 'bass', 'trout', 'halibut', 'striper', 'croaker', 'catfish', 'mackerel'];
  const cautionWords = ['no luck', 'no bites', 'slow', 'frozen', 'windy', 'lost'];
  const catchHits = catchWords.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0);
  const cautionHits = cautionWords.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0);
  let score = 34 + Math.min(24, reportCount * 3) + Math.min(18, catchHits * 4) - Math.min(16, cautionHits * 5);
  const bait = context?.ocean?.baitScore;
  if (typeof bait === 'number' && Number.isFinite(bait)) score += Math.round((bait - 0.42) * 32);
  const current = context?.ocean?.currentSpeed;
  if (typeof current === 'number' && Number.isFinite(current)) score += current > 0.08 && current < 1.8 ? 7 : current >= 1.8 ? -3 : 0;
  const rain = context?.atmosphere?.rainIntensity;
  if (typeof rain === 'number' && Number.isFinite(rain)) score -= Math.round(Math.max(0, rain - 0.22) * 20);
  return Math.max(0, Math.min(100, score));
}

function toneForScore(score: number): LocationMetric['tone'] {
  if (score >= 72) return 'good';
  if (score >= 48) return 'warn';
  return 'neutral';
}

function renderMetric(metric: LocationMetric): string {
  return `
    <div class="intel-metric ${metric.tone ? `is-${metric.tone}` : ''}">
      <span>${escapeHtml(metric.label)}</span>
      <strong>${escapeHtml(metric.value)}</strong>
      ${metric.detail ? `<em>${escapeHtml(metric.detail)}</em>` : ''}
    </div>`;
}

function waterName(water?: SpatialFeature | null): string {
  if (!water) return 'not resolved';
  return water.name || water.label || water.id || 'waterbody';
}

function buildMetrics(report: ReportPoint, context?: LocationIntelContext): LocationMetric[] {
  const score = scoreFromReport(report, context);
  const metrics: LocationMetric[] = [
    { label: 'Best read', value: `${score}%`, detail: 'CSV history + live nearby fields', tone: toneForScore(score) },
  ];
  if (context?.ocean) {
    const ocean = context.ocean;
    if (typeof ocean.baitScore === 'number') metrics.push({ label: 'Bait', value: `${Math.round(ocean.baitScore * 100)}%`, detail: ocean.sampleId, tone: ocean.baitScore > 0.62 ? 'good' : ocean.baitScore > 0.36 ? 'warn' : 'neutral' });
    if (typeof ocean.tempC === 'number' && typeof ocean.tempF === 'number') metrics.push({ label: 'Water temp', value: `${ocean.tempF.toFixed(1)} °F`, detail: `${ocean.tempC.toFixed(1)} °C`, tone: ocean.tempF > 58 && ocean.tempF < 75 ? 'good' : 'neutral' });
    if (typeof ocean.currentSpeed === 'number') metrics.push({ label: 'Current', value: `${ocean.currentSpeed.toFixed(2)}`, detail: `${ocean.currentDirection ?? 'dir ?'} · vector ${ocean.currentVector ?? '?'}`, tone: ocean.currentSpeed > 0.08 ? 'good' : 'neutral' });
    if (typeof ocean.depthM === 'number' && Number.isFinite(ocean.depthM)) metrics.push({ label: 'Bait depth', value: `${ocean.depthM.toFixed(0)} m`, detail: `scalar XYZ z=${(ocean.scalarZ ?? ocean.depthM).toFixed(0)} m`, tone: ocean.depthM > 8 && ocean.depthM < 90 ? 'good' : 'neutral' });
  }
  if (context?.atmosphere) {
    const atm = context.atmosphere;
    if (typeof atm.cloudPct === 'number') metrics.push({ label: 'Clouds', value: `${Math.round(atm.cloudPct)}%`, detail: atm.cloudFamily || atm.validTime, tone: atm.cloudPct > 72 ? 'warn' : 'neutral' });
    if (typeof atm.rainIntensity === 'number') metrics.push({ label: 'Rain', value: `${Math.round(atm.rainIntensity * 100)}%`, detail: atm.validTime, tone: atm.rainIntensity > 0.35 ? 'hot' : 'neutral' });
    if (typeof atm.windSpeed === 'number') metrics.push({ label: 'Wind', value: `${atm.windSpeed.toFixed(1)}`, detail: atm.windDirection ?? 'direction ?', tone: atm.windSpeed > 16 ? 'warn' : 'neutral' });
  }
  metrics.push({ label: 'Waterbody', value: waterName(context?.nearestWater), detail: context?.nearestHarbor ? `near ${waterName(context.nearestHarbor)}` : context?.spatialSource, tone: 'neutral' });
  return metrics;
}

function bestReadSummary(report: ReportPoint, context?: LocationIntelContext): string {
  const score = scoreFromReport(report, context);
  const bits: string[] = [];
  if (score >= 72) bits.push('Strongest current read: this location has useful historic notes and favorable live nearby fields.');
  else if (score >= 48) bits.push('Moderate current read: the old notes are useful, but live field support is mixed or incomplete.');
  else bits.push('Recon read: useful historic location, but the live field score is limited right now.');
  if (context?.ocean?.baitScore !== undefined) bits.push(`Bait ${Math.round(context.ocean.baitScore * 100)}%.`);
  if (context?.ocean?.currentDirection) bits.push(`Current ${context.ocean.currentDirection}.`);
  if (context?.ocean?.depthM !== undefined) bits.push(`Bait scalar depth ${context.ocean.depthM.toFixed(0)} m.`);
  if (context?.atmosphere?.rainIntensity !== undefined && context.atmosphere.rainIntensity > 0.25) bits.push('Rain is active enough to affect visibility/safety.');
  if (report.marine_mask?.classification) bits.push(`Mask: ${report.marine_mask.classification}.`);
  return bits.join(' ');
}

function renderTimeline(report: ReportPoint): string {
  const timeline = timelineEntries(report);
  if (!timeline.length) return '';
  return `
    <section class="intel-section">
      <h4>Original zippy notes</h4>
      <div class="intel-timeline">
        ${timeline.map(([label, value]) => `
          <article class="intel-note">
            <b>${escapeHtml(label)}</b>
            <p>${escapeHtml(value)}</p>
          </article>`).join('')}
      </div>
    </section>`;
}

function renderRawFields(report: ReportPoint): string {
  const entries = reportEntries(report);
  return `
    <details class="intel-raw-fields">
      <summary>All CSV / PostGIS fields (${entries.length})</summary>
      <dl class="location-field-list">
        ${entries.map(([key, value]) => `<dt>${escapeHtml(niceKey(key))}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
      </dl>
    </details>`;
}

function renderContext(context?: LocationIntelContext): string {
  if (!context) return '';
  const rows: Array<[string, string]> = [];
  if (context.spatialSource || context.postgisMode) rows.push(['Spatial source', `${context.spatialSource ?? 'unknown'}${context.postgisMode ? ` · ${context.postgisMode}` : ''}`]);
  if (context.bboxLabel) rows.push(['Viewport', context.bboxLabel]);
  if (context.ocean?.distanceKm !== undefined) rows.push(['Ocean sample distance', `${context.ocean.distanceKm.toFixed(1)} km`]);
  if (context.ocean?.depthM !== undefined) rows.push(['Ocean XYZ depth', `${context.ocean.depthM.toFixed(0)} m positive-down`]);
  if (context.atmosphere?.distanceKm !== undefined) rows.push(['Atmosphere sample distance', `${context.atmosphere.distanceKm.toFixed(1)} km`]);
  if (context.counts) rows.push(['Viewport counts', `${context.counts.locations ?? 0} locations · ${context.counts.waterbodies ?? 0} waters · ${context.counts.harbors ?? 0} harbors`]);
  if (!rows.length) return '';
  return `
    <section class="intel-section compact">
      <h4>Live context</h4>
      <dl class="intel-context-list">
        ${rows.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
      </dl>
    </section>`;
}

export function createIntelligencePane(): {
  element: HTMLElement;
  log: (event: FieldStreamEvent | string) => void;
  renderReports: (reports: ReportPoint[]) => void;
  selectReport: (report: ReportPoint, context?: LocationIntelContext) => void;
  selectSharkIntel: (intel: SharkIntelSelection) => void;
} {
  const element = document.createElement('aside');
  element.className = 'intelligence-pane location-glass-pane is-hidden';
  element.innerHTML = `
    <button class="pane-close" type="button" aria-label="Close location pane">×</button>
    <h2>Location Intel</h2>
    <section class="selected-report"></section>
  `;
  const heading = element.querySelector<HTMLElement>('h2')!;
  const selected = element.querySelector<HTMLElement>('.selected-report')!;
  const close = element.querySelector<HTMLButtonElement>('.pane-close')!;
  close.onclick = () => element.classList.add('is-hidden');
  return {
    element,
    log(_event) {
      // Quiet by default. This pane is for selected CSV/PostGIS locations and shark intel,
      // not live debug printouts.
    },
    renderReports(_reports) {
      // Locations are displayed as clickable green orbs on the globe. The pane opens only on click.
    },
    selectReport(report, context) {
      heading.textContent = 'Location Intel';
      const coordinate = `${report.latitude.toFixed(5)}, ${report.longitude.toFixed(5)}`;
      const metrics = buildMetrics(report, context);
      selected.innerHTML = `
        <div class="intel-head">
          <h3>${escapeHtml(report.title)}</h3>
          <div class="location-meta">${escapeHtml(report.source)} · ${escapeHtml(coordinate)}</div>
        </div>
        <section class="intel-best-read">
          <span>Best Intel</span>
          <p>${escapeHtml(bestReadSummary(report, context))}</p>
        </section>
        <section class="intel-metric-grid">
          ${metrics.map(renderMetric).join('')}
        </section>
        ${renderTimeline(report)}
        ${renderContext(context)}
        ${renderRawFields(report)}
      `;
      element.classList.remove('is-hidden');
    },
    selectSharkIntel(intel) {
      heading.textContent = 'Shark Intel';
      const coordinate = `${intel.lat.toFixed(5)}, ${intel.lon.toFixed(5)}`;
      const pct = Math.round(Math.max(0, Math.min(1, intel.score)) * 100);
      selected.innerHTML = `
        <h3>${escapeHtml(intel.title)}</h3>
        <div class="location-meta">${escapeHtml(intel.source)} · ${escapeHtml(coordinate)}</div>
        <div class="shark-prediction-score">Area prediction: ${pct}%</div>
        <p class="shark-prediction-summary">${escapeHtml(intel.summary)}</p>
        <dl class="location-field-list shark-field-list">
          ${intel.evidence.map(([key, value]) => `<dt>${escapeHtml(niceKey(key))}</dt><dd>${escapeHtml(value)}</dd>`).join('')}
        </dl>
      `;
      element.classList.remove('is-hidden');
    },
  };
}
