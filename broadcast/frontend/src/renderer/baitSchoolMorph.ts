import type { FieldSample } from '../fields/sampler';
import type { MarkerSpec, PolygonSpec, PolylineSpec } from './google3d';
import { ellipsePath, polygonSpec } from './geometryPrimitives';
import type { BaitRenderFeature, OceanFeaturePayload } from './baitLegacyVisual';
import { buildMergedBaitFeatures } from './baitLegacyVisual';

export interface BaitMorphFrame {
  polygons: PolygonSpec[];
  polylines: PolylineSpec[];
  markers: MarkerSpec[];
  summary: string;
  visibleSchools: number;
  particleCount: number;
}

type SchoolState = BaitRenderFeature & {
  opacity: number;
  target: BaitRenderFeature;
  lastSeenMs: number;
  updatedMs: number;
  seed: number;
  particleCount: number;
};

function finite(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

function hashNumber(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

function rand(seed: number, offset: number): number {
  const x = Math.sin(seed * 991.71 + offset * 77.13) * 43758.5453123;
  return x - Math.floor(x);
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function signedAngle(u: number, v: number): number {
  return Math.atan2(v || 0.12, u || 0.32);
}

function metersToDegreesLat(meters: number): number {
  return meters / 111_320;
}

function metersToDegreesLon(meters: number, lat: number): number {
  return meters / Math.max(11_000, 111_320 * Math.cos((lat * Math.PI) / 180));
}

function particleBudget(feature: BaitRenderFeature): number {
  const base = feature.source === 'ocean-feature-cluster' ? 28 : 16;
  const areaBoost = Math.min(48, Math.round((feature.radiusM + feature.radiusYM) / 260));
  const scoreBoost = Math.round(clamp(feature.score) * 34);
  const count = Math.max(12, Math.min(96, base + areaBoost + scoreBoost));
  return count % 2 === 0 ? count : count + 1;
}

function advectDegrees(u: number, v: number, lat: number, dtSeconds: number): { dLat: number; dLon: number } {
  // Current vectors are m/s.  We visibly advance only a fraction of the true drift
  // so retained bait schools move smoothly without racing across the 3D globe.
  const visualSeconds = dtSeconds * 0.22;
  return {
    dLat: metersToDegreesLat(v * visualSeconds),
    dLon: metersToDegreesLon(u * visualSeconds, lat),
  };
}

export class BaitSchoolMorphController {
  private states = new Map<string, SchoolState>();
  private lastFrameMs = performance.now();

  clear(): void {
    this.states.clear();
  }

  update(samples: FieldSample[], payload?: OceanFeaturePayload | null, nowMs = performance.now()): void {
    const incoming = buildMergedBaitFeatures(samples, payload ?? undefined, 72);
    for (const feature of incoming) {
      const seed = hashNumber(feature.id);
      const existing = this.states.get(feature.id);
      if (existing) {
        existing.target = feature;
        existing.lastSeenMs = nowMs;
        existing.particleCount = Math.max(existing.particleCount, particleBudget(feature));
      } else {
        this.states.set(feature.id, {
          ...feature,
          target: feature,
          opacity: 0.02,
          lastSeenMs: nowMs,
          updatedMs: nowMs,
          seed,
          particleCount: particleBudget(feature),
        });
      }
    }
  }

  frame(nowMs = performance.now(), options: { morphSeconds?: number; holdMs?: number; fadeOutMs?: number } = {}): BaitMorphFrame {
    const morphSeconds = options.morphSeconds ?? 26;
    const holdMs = options.holdMs ?? 42_000;
    const fadeOutMs = options.fadeOutMs ?? 95_000;
    const dtSeconds = Math.max(0.001, Math.min(2.5, (nowMs - this.lastFrameMs) / 1000));
    this.lastFrameMs = nowMs;
    const t = clamp(dtSeconds / morphSeconds, 0.025, 0.18);
    const polygons: PolygonSpec[] = [];
    const polylines: PolylineSpec[] = [];
    const markers: MarkerSpec[] = [];
    let particleCount = 0;
    let visibleSchools = 0;

    for (const [id, state] of Array.from(this.states)) {
      const missingMs = nowMs - state.lastSeenMs;
      const targetOpacity = missingMs <= holdMs ? 1 : Math.max(0, 1 - (missingMs - holdMs) / fadeOutMs);
      if (targetOpacity <= 0.01) {
        this.states.delete(id);
        continue;
      }
      const drift = advectDegrees(state.currentU, state.currentV, state.lat, dtSeconds);
      state.lat = lerp(state.lat + drift.dLat, state.target.lat, t);
      state.lon = lerp(state.lon + drift.dLon, state.target.lon, t);
      state.score = lerp(state.score, state.target.score, t);
      state.radiusM = lerp(state.radiusM, state.target.radiusM, t);
      state.radiusYM = lerp(state.radiusYM, state.target.radiusYM, t);
      state.altitudeM = lerp(state.altitudeM, state.target.altitudeM, t);
      state.currentU = lerp(state.currentU, state.target.currentU, t);
      state.currentV = lerp(state.currentV, state.target.currentV, t);
      state.depthM = lerp(finite(state.depthM, 0), finite(state.target.depthM, 0), t);
      state.opacity = lerp(state.opacity, targetOpacity, 0.12);
      visibleSchools += 1;
      const rendered = this.renderSchool(state);
      polygons.push(...rendered.polygons);
      polylines.push(...rendered.polylines);
      markers.push(...rendered.markers);
      particleCount += rendered.markers.length;
    }

    const top = Array.from(this.states.values()).reduce((max, state) => Math.max(max, state.score), 0);
    return {
      polygons,
      polylines,
      markers,
      visibleSchools,
      particleCount,
      summary: `Bait morph: ${visibleSchools} retained schools, ${particleCount} mirror 4–8 inch particles, top score ${top.toFixed(2)}, orange shells advecting/morphing with ocean XYZ depth`,
    };
  }

  private renderSchool(feature: SchoolState): { polygons: PolygonSpec[]; polylines: PolylineSpec[]; markers: MarkerSpec[] } {
    const opacity = clamp(feature.opacity);
    const score = clamp(feature.score);
    const heading = signedAngle(feature.currentU, feature.currentV);
    const depthM = Math.max(0, finite(feature.depthM, 0));
    const depthDrop = Math.min(220, depthM * 1.4);
    const baseAlt = Math.max(26, feature.altitudeM - depthDrop * 0.22);
    const shellAlpha = (0.07 + score * 0.17) * opacity;
    const strokeAlpha = (0.25 + score * 0.42) * opacity;
    const shellTitle = `${feature.title} · depth ${depthM.toFixed(0)} m · scalar XYZ school shell · particles hold count ${feature.particleCount}`;
    const shellRoughness = feature.source === 'ocean-feature-cluster' ? 0.08 : 0.045;
    const polygons: PolygonSpec[] = [
      {
        ...polygonSpec(
          `bait-school:${feature.id}:orange-shell-outer`,
          ellipsePath({
            lat: feature.lat,
            lon: feature.lon,
            altitudeM: baseAlt + 38,
            radiusXM: feature.radiusM * 1.18,
            radiusYM: feature.radiusYM * 1.22,
            rotationRad: heading,
            segments: 32,
            scallop: shellRoughness,
            seed: feature.seed,
          }),
          `rgba(251,146,60,${shellAlpha.toFixed(3)})`,
          `rgba(253,186,116,${strokeAlpha.toFixed(3)})`,
          1.15 + score * 1.1,
          shellTitle,
        ),
        altitudeMode: 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
        zIndex: 35,
      },
      {
        ...polygonSpec(
          `bait-school:${feature.id}:orange-shell-depth`,
          ellipsePath({
            lat: feature.lat + Math.sin(heading) * metersToDegreesLat(feature.radiusYM * 0.06),
            lon: feature.lon + Math.cos(heading) * metersToDegreesLon(feature.radiusYM * 0.06, feature.lat),
            altitudeM: Math.max(22, baseAlt - Math.min(145, depthM * 0.58)),
            radiusXM: feature.radiusM * 0.94,
            radiusYM: feature.radiusYM * 0.96,
            rotationRad: heading + 0.05,
            segments: 28,
            scallop: shellRoughness * 0.65,
            seed: feature.seed + 4.7,
          }),
          `rgba(249,115,22,${(shellAlpha * 0.66).toFixed(3)})`,
          `rgba(255,237,213,${(strokeAlpha * 0.52).toFixed(3)})`,
          0.72 + score * 0.75,
          `${shellTitle} · lower depth envelope`,
        ),
        altitudeMode: 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
        zIndex: 32,
      },
    ];

    const speed = Math.hypot(feature.currentU, feature.currentV);
    const polylines: PolylineSpec[] = speed > 0.02 ? [{
      id: `bait-school:${feature.id}:advection`,
      path: [
        { lat: feature.lat - feature.currentV * 0.006, lng: feature.lon - feature.currentU * 0.006, altitude: Math.max(24, baseAlt - 12) },
        { lat: feature.lat + feature.currentV * 0.017, lng: feature.lon + feature.currentU * 0.017, altitude: baseAlt + 72 },
      ],
      strokeColor: `rgba(255,237,213,${(0.28 + score * 0.28).toFixed(3)})`,
      outerColor: `rgba(251,146,60,${(0.13 + score * 0.24).toFixed(3)})`,
      strokeWidth: 1.25 + score * 2.4,
      altitudeMode: 'RELATIVE_TO_GROUND',
    }] : [];

    const markers: MarkerSpec[] = [];
    const count = feature.particleCount;
    const particleSizeIn = 4 + score * 4;
    for (let i = 0; i < count; i += 1) {
      const r = Math.sqrt(rand(feature.seed, i * 2 + 1)) * 0.86;
      const a = rand(feature.seed, i * 2 + 2) * Math.PI * 2;
      const localX = Math.cos(a) * r * feature.radiusM * 0.83;
      const localY = Math.sin(a) * r * feature.radiusYM * 0.80;
      const rotX = Math.cos(heading) * localX - Math.sin(heading) * localY;
      const rotY = Math.sin(heading) * localX + Math.cos(heading) * localY;
      const particleDepth = depthM * (0.16 + rand(feature.seed, i * 3 + 3) * 0.84);
      const shimmer = rand(feature.seed, i * 5 + 9);
      markers.push({
        id: `bait-school:${feature.id}:particle:${i}`,
        lat: feature.lat + metersToDegreesLat(rotY),
        lon: feature.lon + metersToDegreesLon(rotX, feature.lat),
        altitude: Math.max(16, baseAlt + 34 + shimmer * 80 - Math.min(185, particleDepth * 0.7)),
        label: shimmer > 0.52 ? '◐' : '◑',
        title: `${feature.title} · mirror silver/white bait particle ${i + 1}/${count} · ${particleSizeIn.toFixed(1)} in · depth ${particleDepth.toFixed(0)} m`,
        className: 'bait-school-particle',
        color: shimmer > 0.52 ? '#f8fafc' : '#e5e7eb',
        glowColor: shimmer > 0.52 ? 'rgba(255,255,255,.86)' : 'rgba(203,213,225,.74)',
        scale: 0.38 + score * 0.32 + shimmer * 0.12,
        opacity: clamp((0.34 + score * 0.46) * opacity, 0, 0.92),
      });
    }
    return { polygons, polylines, markers };
  }
}
