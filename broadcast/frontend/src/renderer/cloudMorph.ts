import type { PolygonSpec } from './google3d';

interface CloudMorphEntry {
  id: string;
  current: PolygonSpec;
  target: PolygonSpec;
  lastSeenMs: number;
  createdMs: number;
  missingSinceMs: number | null;
}

export interface CloudMorphStats {
  visible: number;
  target: number;
  retained: number;
  fading: number;
}

export interface CloudMorphOptions {
  nowMs?: number;
  fadeInMs?: number;
  fadeOutMs?: number;
  holdMs?: number;
  morphSeconds?: number;
}

const DEFAULT_FADE_IN_MS = 14_000;
const DEFAULT_FADE_OUT_MS = 70_000;
const DEFAULT_HOLD_MS = 28_000;
const DEFAULT_MORPH_SECONDS = 34;
const EARTH_METERS_PER_DEGREE = 111_320;

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function damp(current: number, target: number, deltaSeconds: number, smoothingSeconds = DEFAULT_MORPH_SECONDS): number {
  if (!Number.isFinite(current)) return target;
  if (!Number.isFinite(target)) return current;
  const t = 1 - Math.exp(-Math.max(0, deltaSeconds) / Math.max(0.001, smoothingSeconds));
  return current + (target - current) * clamp(t, 0, 1);
}

function centroid(path: PolygonSpec['path']): { lat: number; lng: number; altitude: number } {
  if (!path.length) return { lat: 0, lng: 0, altitude: 0 };
  let lat = 0;
  let lng = 0;
  let altitude = 0;
  for (const point of path) {
    lat += Number(point.lat) || 0;
    lng += Number(point.lng) || 0;
    altitude += Number(point.altitude) || 0;
  }
  const n = path.length;
  return { lat: lat / n, lng: lng / n, altitude: altitude / n };
}

function advectPath(path: PolygonSpec['path'], windU = 0, windV = 0, seconds = 0): PolygonSpec['path'] {
  if (!seconds || (!windU && !windV)) return path;
  const c = centroid(path);
  const latMetersPerDeg = EARTH_METERS_PER_DEGREE;
  const lonMetersPerDeg = EARTH_METERS_PER_DEGREE * Math.max(0.18, Math.cos((c.lat * Math.PI) / 180));
  const dLat = (windV * seconds) / latMetersPerDeg;
  const dLng = (windU * seconds) / lonMetersPerDeg;
  return path.map((point) => ({ ...point, lat: point.lat + dLat, lng: point.lng + dLng }));
}

function interpolatePath(current: PolygonSpec['path'], target: PolygonSpec['path'], deltaSeconds: number, smoothingSeconds: number): PolygonSpec['path'] {
  if (!current.length || current.length !== target.length) return target;
  return current.map((point, index) => {
    const next = target[index];
    return {
      lat: damp(point.lat, next.lat, deltaSeconds, smoothingSeconds),
      lng: damp(point.lng, next.lng, deltaSeconds, smoothingSeconds),
      altitude: point.altitude === undefined && next.altitude === undefined
        ? undefined
        : damp(point.altitude ?? next.altitude ?? 0, next.altitude ?? point.altitude ?? 0, deltaSeconds, smoothingSeconds),
    };
  });
}

function multiplyRgbaAlpha(color: string, multiplier: number): string {
  const m = color.match(/^rgba\(([^,]+),([^,]+),([^,]+),([^\)]+)\)$/i);
  if (!m) return color;
  const alpha = clamp(Number(m[4]) * multiplier, 0, 1);
  return `rgba(${m[1].trim()},${m[2].trim()},${m[3].trim()},${alpha.toFixed(3)})`;
}

function fadeSpec(spec: PolygonSpec, alphaMultiplier: number): PolygonSpec {
  const a = clamp(alphaMultiplier, 0, 1);
  return {
    ...spec,
    fillColor: multiplyRgbaAlpha(spec.fillColor, a),
    strokeColor: multiplyRgbaAlpha(spec.strokeColor, Math.min(1, a * 0.9 + 0.1)),
  };
}

function windU(spec: PolygonSpec): number {
  return Number((spec as unknown as { advectU?: number }).advectU ?? 0) || 0;
}

function windV(spec: PolygonSpec): number {
  return Number((spec as unknown as { advectV?: number }).advectV ?? 0) || 0;
}

function cloneSpec(spec: PolygonSpec): PolygonSpec {
  return { ...spec, path: spec.path.map((point) => ({ ...point })) };
}

function cloudLayerSuffix(id: string): string {
  const pieces = id.split(':');
  return pieces[pieces.length - 1] ?? id;
}

function distanceDeg(a: PolygonSpec, b: PolygonSpec): number {
  const ca = centroid(a.path);
  const cb = centroid(b.path);
  const dx = (ca.lng - cb.lng) * Math.max(0.18, Math.cos((ca.lat * Math.PI) / 180));
  const dy = ca.lat - cb.lat;
  return Math.hypot(dx, dy);
}

/**
 * Persistent cloud renderer state.
 *
 * The old path was: each SSE event produced a complete polygon list and
 * syncPolygons() dropped anything not in that new list.  That makes GFS/PostGIS
 * regeneration look like a flash.  This stateful reducer treats each cloud
 * body as an alive object: new targets fade in, existing objects morph toward
 * the new paths, and missing objects hold/advect/fade out instead of being
 * removed immediately.
 */
export class CloudMorphController {
  private readonly entries = new Map<string, CloudMorphEntry>();
  private lastFrameMs = 0;
  private lastTargetIds = new Set<string>();
  stats: CloudMorphStats = { visible: 0, target: 0, retained: 0, fading: 0 };

  updateTarget(targetSpecs: PolygonSpec[], options: CloudMorphOptions = {}): void {
    const nowMs = options.nowMs ?? performance.now();
    const incomingIds = new Set<string>();
    const reusableOldIds = new Set(this.entries.keys());

    for (const rawSpec of targetSpecs) {
      const spec = cloneSpec(rawSpec);
      let id = spec.id;
      let existing = this.entries.get(id);

      // If the backend/PostGIS regenerated cloud IDs, crossfade is safe; but
      // when a nearby same-layer cloud is clearly the same visual body, reuse
      // the old key so the DOM element itself morphs instead of being replaced.
      if (!existing) {
        let bestId = '';
        let bestDistance = Number.POSITIVE_INFINITY;
        for (const oldId of reusableOldIds) {
          const old = this.entries.get(oldId);
          if (!old || incomingIds.has(oldId)) continue;
          if (cloudLayerSuffix(old.current.id) !== cloudLayerSuffix(spec.id)) continue;
          const d = distanceDeg(old.current, spec);
          if (d < bestDistance) {
            bestId = oldId;
            bestDistance = d;
          }
        }
        if (bestId && bestDistance < 0.22) {
          existing = this.entries.get(bestId);
          id = bestId;
          spec.id = id;
        }
      }

      incomingIds.add(id);
      if (existing) {
        existing.target = spec;
        existing.lastSeenMs = nowMs;
        existing.missingSinceMs = null;
      } else {
        this.entries.set(id, {
          id,
          current: fadeSpec(spec, 0.01),
          target: spec,
          createdMs: nowMs,
          lastSeenMs: nowMs,
          missingSinceMs: null,
        });
      }
      reusableOldIds.delete(id);
    }

    for (const [id, entry] of this.entries) {
      if (incomingIds.has(id)) continue;
      if (entry.missingSinceMs === null) entry.missingSinceMs = nowMs;
    }
    this.lastTargetIds = incomingIds;
  }

  frame(options: CloudMorphOptions = {}): PolygonSpec[] {
    const nowMs = options.nowMs ?? performance.now();
    const fadeInMs = options.fadeInMs ?? DEFAULT_FADE_IN_MS;
    const fadeOutMs = options.fadeOutMs ?? DEFAULT_FADE_OUT_MS;
    const holdMs = options.holdMs ?? DEFAULT_HOLD_MS;
    const morphSeconds = options.morphSeconds ?? DEFAULT_MORPH_SECONDS;
    const deltaSeconds = this.lastFrameMs ? Math.max(0.001, (nowMs - this.lastFrameMs) / 1000) : 0.001;
    this.lastFrameMs = nowMs;

    const visible: PolygonSpec[] = [];
    let retained = 0;
    let fading = 0;

    for (const [id, entry] of Array.from(this.entries)) {
      const missingMs = entry.missingSinceMs === null ? 0 : nowMs - entry.missingSinceMs;
      if (entry.missingSinceMs !== null && missingMs > holdMs + fadeOutMs) {
        this.entries.delete(id);
        continue;
      }

      const targetPath = entry.missingSinceMs === null
        ? entry.target.path
        : advectPath(entry.current.path, windU(entry.current), windV(entry.current), deltaSeconds);
      entry.current = {
        ...entry.current,
        ...entry.target,
        id: entry.id,
        path: interpolatePath(entry.current.path, targetPath, deltaSeconds, morphSeconds),
      };

      let alpha = clamp((nowMs - entry.createdMs) / fadeInMs, 0.01, 1);
      if (entry.missingSinceMs !== null) {
        retained += 1;
        const fadeAge = Math.max(0, missingMs - holdMs);
        const fade = 1 - clamp(fadeAge / fadeOutMs, 0, 1);
        alpha *= fade;
        if (fadeAge > 0) fading += 1;
      }
      if (alpha > 0.01) visible.push(fadeSpec(entry.current, alpha));
    }

    this.stats = { visible: visible.length, target: this.lastTargetIds.size, retained, fading };
    return visible;
  }

  clear(): void {
    this.entries.clear();
    this.lastTargetIds = new Set();
    this.stats = { visible: 0, target: 0, retained: 0, fading: 0 };
  }

  get active(): boolean {
    return this.entries.size > 0;
  }
}
