import type { FieldSample } from '../fields/sampler';
import type { MarkerSpec, PolygonSpec, PolylineSpec } from './google3d';
import { ellipsePath, polygonSpec } from './geometryPrimitives';

export interface OceanFeaturePayload {
  ok?: boolean;
  source?: string;
  valid_time?: string;
  current_vector_count?: number;
  bait_cluster_count?: number;
  current_vectors?: Array<{ id?: string; lat?: number; lon?: number; lng?: number; u?: number; v?: number; speed?: number; depth_m?: number }>;
  bait_clusters?: Array<{
    id?: string;
    centroid?: { lat?: number; lon?: number; lng?: number };
    bbox?: { west?: number; south?: number; east?: number; north?: number };
    area_cells?: number;
    score?: number;
    score_max?: number;
    depth_m?: number;
    render_hint?: string;
  }>;
}

export interface BaitRenderFeature {
  id: string;
  lat: number;
  lon: number;
  score: number;
  radiusM: number;
  radiusYM: number;
  altitudeM: number;
  currentU: number;
  currentV: number;
  sstC?: number;
  depthM?: number;
  source: 'ocean-feature-cluster' | 'ocean-field-sample';
  title: string;
}

function finite(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.max(min, Math.min(max, value));
}

function valueFrom(sample: FieldSample, names: string[], fallback = 0): number {
  for (const name of names) {
    const value = sample.values[name];
    if (Number.isFinite(value)) return value;
  }
  return fallback;
}

function nearestCurrent(lat: number, lon: number, payload?: OceanFeaturePayload): { u: number; v: number; speed: number } {
  let best: { u: number; v: number; speed: number; d2: number } | null = null;
  for (const vector of payload?.current_vectors ?? []) {
    const vLat = finite(vector.lat, NaN);
    const vLon = finite(vector.lon ?? vector.lng, NaN);
    if (!Number.isFinite(vLat) || !Number.isFinite(vLon)) continue;
    const dLat = vLat - lat;
    const dLon = vLon - lon;
    const d2 = dLat * dLat + dLon * dLon;
    if (best && best.d2 <= d2) continue;
    const u = finite(vector.u, 0);
    const v = finite(vector.v, 0);
    best = { u, v, speed: finite(vector.speed, Math.hypot(u, v)), d2 };
  }
  return best ?? { u: 0, v: 0, speed: 0 };
}

function radiusFromClusterBBox(cluster: NonNullable<OceanFeaturePayload['bait_clusters']>[number], score: number): { x: number; y: number } {
  const bbox = cluster.bbox;
  if (!bbox) return { x: 1800 + score * 4200, y: 700 + score * 2100 };
  const west = finite(bbox.west, NaN);
  const east = finite(bbox.east, NaN);
  const south = finite(bbox.south, NaN);
  const north = finite(bbox.north, NaN);
  if (![west, east, south, north].every(Number.isFinite)) return { x: 1800 + score * 4200, y: 700 + score * 2100 };
  const centerLat = (south + north) / 2;
  const metersPerDegreeLon = Math.max(12_000, 111_320 * Math.cos((centerLat * Math.PI) / 180));
  const width = Math.max(900, Math.abs(east - west) * metersPerDegreeLon * 0.54);
  const height = Math.max(450, Math.abs(north - south) * 111_320 * 0.54);
  return { x: Math.min(9000, width + score * 2600), y: Math.min(4800, height + score * 1300) };
}

export function buildMergedBaitFeatures(samples: FieldSample[], payload?: OceanFeaturePayload, maxCount = 56): BaitRenderFeature[] {
  const features: BaitRenderFeature[] = [];

  for (const [index, cluster] of (payload?.bait_clusters ?? []).entries()) {
    const centroid = cluster.centroid ?? {};
    const lat = finite(centroid.lat, NaN);
    const lon = finite(centroid.lon ?? centroid.lng, NaN);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const score = clamp(Math.max(finite(cluster.score, 0), finite(cluster.score_max, 0)));
    if (score < 0.35) continue;
    const current = nearestCurrent(lat, lon, payload);
    const radius = radiusFromClusterBBox(cluster, score);
    const depthM = finite(cluster.depth_m, 0);
    features.push({
      id: `cluster:${cluster.id ?? index}`,
      lat,
      lon,
      score,
      radiusM: radius.x,
      radiusYM: radius.y,
      altitudeM: 82 + score * 155 + Math.min(120, Math.max(0, depthM) * 0.55),
      currentU: current.u,
      currentV: current.v,
      depthM,
      source: 'ocean-feature-cluster',
      title: `bait cluster ${score.toFixed(2)} · ${cluster.area_cells ?? '?'} cells · merged old glow/new ocean truth`,
    });
  }

  const occupied = (lat: number, lon: number): boolean => features.some((feature) => {
    const dLat = feature.lat - lat;
    const dLon = feature.lon - lon;
    return dLat * dLat + dLon * dLon < 0.0065;
  });

  for (const sample of samples) {
    const score = clamp(valueFrom(sample, ['bait_score'], 0));
    if (score < 0.34 || occupied(sample.lat, sample.lon)) continue;
    const u = valueFrom(sample, ['current_u', 'u'], 0);
    const v = valueFrom(sample, ['current_v', 'v'], 0);
    const speed = valueFrom(sample, ['current_speed'], Math.hypot(u, v));
    const sstC = valueFrom(sample, ['sst_c', 'water_temp_c'], NaN);
    const depthM = valueFrom(sample, ['bait_depth_m', 'depth_m'], 0);
    features.push({
      id: `sample:${sample.id}`,
      lat: sample.lat,
      lon: sample.lon,
      score,
      radiusM: 900 + score * 3300 + Math.min(900, speed * 320),
      radiusYM: 360 + score * 1650,
      altitudeM: 58 + score * 110 + Math.min(95, Math.max(0, depthM) * 0.35),
      currentU: u,
      currentV: v,
      sstC: Number.isFinite(sstC) ? sstC : undefined,
      depthM,
      source: 'ocean-field-sample',
      title: `bait score ${score.toFixed(2)} · ${Number.isFinite(sstC) ? `${sstC.toFixed(1)}°C · ` : ''}${Math.hypot(u, v).toFixed(2)} current`,
    });
    if (features.length >= maxCount) break;
  }

  return features.sort((a, b) => b.score - a.score).slice(0, maxCount);
}

function baitFill(feature: BaitRenderFeature, alpha: number): string {
  const score = clamp(feature.score);
  if (score > 0.78) return `rgba(250,204,21,${alpha})`;
  if (score > 0.58) return `rgba(52,211,153,${alpha})`;
  return `rgba(45,212,191,${alpha})`;
}

function baitStroke(feature: BaitRenderFeature, alpha: number): string {
  const score = clamp(feature.score);
  if (score > 0.78) return `rgba(254,240,138,${alpha})`;
  if (score > 0.58) return `rgba(187,247,208,${alpha})`;
  return `rgba(153,246,228,${alpha})`;
}

export function baitLegacyPolygons(features: BaitRenderFeature[]): PolygonSpec[] {
  const polygons: PolygonSpec[] = [];
  for (const [index, feature] of features.entries()) {
    const heading = Math.atan2(feature.currentV || 0.18, feature.currentU || 0.42);
    const phase = index * 0.73 + feature.score * 2.1;
    const sourceBoost = feature.source === 'ocean-feature-cluster' ? 1.16 : 1;
    const layerDefs = [
      { suffix: 'legacy-halo', scaleX: 1.55 * sourceBoost, scaleY: 1.28, altitude: feature.altitudeM - 8, alpha: 0.10 + feature.score * 0.18, stroke: 0.26, width: 0.7, scallop: 0.07 },
      { suffix: 'legacy-body', scaleX: 1.00 * sourceBoost, scaleY: 1.00, altitude: feature.altitudeM + 12, alpha: 0.18 + feature.score * 0.30, stroke: 0.46, width: 1.4, scallop: 0.12 },
      { suffix: 'legacy-core', scaleX: 0.45 * sourceBoost, scaleY: 0.38, altitude: feature.altitudeM + 34, alpha: 0.24 + feature.score * 0.34, stroke: 0.58, width: 1.1, scallop: 0.06 },
    ];
    for (const layer of layerDefs) {
      polygons.push({
        ...polygonSpec(
          `bait-merged:${feature.id}:${layer.suffix}`,
          ellipsePath({
            lat: feature.lat,
            lon: feature.lon,
            altitudeM: Math.max(28, layer.altitude),
            radiusXM: feature.radiusM * layer.scaleX,
            radiusYM: feature.radiusYM * layer.scaleY,
            rotationRad: heading + phase * 0.08,
            segments: feature.source === 'ocean-feature-cluster' ? 28 : 22,
            scallop: layer.scallop,
            seed: phase,
          }),
          baitFill(feature, layer.alpha),
          baitStroke(feature, layer.stroke),
          layer.width + feature.score * 0.9,
          feature.title,
        ),
        altitudeMode: 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
        zIndex: 20 + index,
      });
    }

    if (feature.score > 0.62) {
      polygons.push({
        ...polygonSpec(
          `bait-merged:${feature.id}:side-depth-sheet`,
          ellipsePath({
            lat: feature.lat + Math.sin(heading) * 0.004,
            lon: feature.lon + Math.cos(heading) * 0.004,
            altitudeM: Math.max(38, feature.altitudeM + 55),
            radiusXM: feature.radiusM * 0.34,
            radiusYM: feature.radiusYM * 0.92,
            rotationRad: heading + Math.PI / 2,
            segments: 18,
            scallop: 0.08,
            seed: phase + 1.2,
          }),
          `rgba(20,184,166,${(0.10 + feature.score * 0.16).toFixed(3)})`,
          baitStroke(feature, 0.32),
          0.8,
          `${feature.title} · side-depth glow`,
        ),
        altitudeMode: 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
        zIndex: 42 + index,
      });
    }
  }
  return polygons;
}

export function baitLegacyDriftLines(features: BaitRenderFeature[]): PolylineSpec[] {
  const lines: PolylineSpec[] = [];
  for (const [index, feature] of features.filter((f) => Math.hypot(f.currentU, f.currentV) > 0.03).slice(0, 40).entries()) {
    const speed = Math.hypot(feature.currentU, feature.currentV);
    const scale = 0.018 + Math.min(0.045, speed * 0.020);
    lines.push({
      id: `bait-merged-drift:${feature.id}:${index}`,
      path: [
        { lat: feature.lat - feature.currentV * scale * 0.42, lng: feature.lon - feature.currentU * scale * 0.42, altitude: Math.max(22, feature.altitudeM - 18) },
        { lat: feature.lat + feature.currentV * scale, lng: feature.lon + feature.currentU * scale, altitude: feature.altitudeM + 42 },
      ],
      strokeColor: baitStroke(feature, 0.52),
      outerColor: baitFill(feature, 0.20),
      strokeWidth: 1.5 + feature.score * 3.2,
      altitudeMode: 'RELATIVE_TO_GROUND',
    });
  }
  return lines;
}

export function baitLegacyMarkers(features: BaitRenderFeature[]): MarkerSpec[] {
  return features
    .filter((feature) => feature.score > 0.50)
    .slice(0, 42)
    .map((feature, index) => ({
      id: `bait-merged-spark:${feature.id}:${index}`,
      lat: feature.lat,
      lon: feature.lon,
      altitude: feature.altitudeM + 95 + feature.score * 70,
      label: feature.score > 0.78 ? '✦' : '•',
      title: feature.title,
      className: 'legacy-bait-glow-marker',
      color: feature.score > 0.78 ? '#fde047' : '#5eead4',
      glowColor: feature.score > 0.78 ? 'rgba(250,204,21,.86)' : 'rgba(45,212,191,.82)',
      scale: 0.86 + feature.score * 1.05,
      opacity: 0.52 + feature.score * 0.34,
    }));
}

export function baitLegacySummary(features: BaitRenderFeature[]): string {
  const clusters = features.filter((feature) => feature.source === 'ocean-feature-cluster').length;
  const samples = features.length - clusters;
  const top = features[0]?.score ?? 0;
  return `Bait renderer merge: ${features.length} old-style glow fields from ${clusters} ocean clusters + ${samples} field samples, top score ${top.toFixed(2)}`;
}
