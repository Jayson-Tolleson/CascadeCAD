import type { FieldSample } from '../fields/sampler';
import type { BoatEntity } from '../types/layers';
import type { MarkerSpec, ModelSpec, PolygonSpec, PolylineSpec } from './google3d';
import { ellipsePath, polygonSpec, trianglePath } from './geometryPrimitives';

export interface BoatRenderFeature {
  id: string;
  lat: number;
  lon: number;
  headingDeg: number;
  currentU: number;
  currentV: number;
  currentKt: number;
  safety: 'good' | 'caution' | 'rough' | 'unknown';
  model: string;
  title: string;
}

export interface BoatHazardFeature {
  id: string;
  lat: number;
  lon: number;
  currentKt: number;
  baitScore: number;
  depthM: number;
  risk: number;
}

export const SHIP2_MODEL_SRC = '/models/ship2.gltf';

function finite(value: unknown, fallback = 0): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeSafety(value: unknown): BoatRenderFeature['safety'] {
  const text = String(value ?? '').toLowerCase();
  if (text.includes('rough') || text.includes('danger')) return 'rough';
  if (text.includes('caution') || text.includes('warn')) return 'caution';
  if (text.includes('good') || text.includes('safe')) return 'good';
  return 'unknown';
}


const BOAT_HARBOR_ALLOW_BOXES = [
  { name: 'san_diego_bay', west: -117.28, south: 32.58, east: -117.08, north: 32.76 },
  { name: 'mission_bay', west: -117.27, south: 32.75, east: -117.18, north: 32.82 },
  { name: 'los_angeles_long_beach_harbor', west: -118.32, south: 33.68, east: -118.05, north: 33.83 },
  { name: 'newport_bay', west: -117.94, south: 33.58, east: -117.84, north: 33.64 },
  { name: 'anaheim_huntington_harbour', west: -118.08, south: 33.70, east: -118.00, north: 33.75 },
  { name: 'monterey_bay', west: -122.15, south: 36.55, east: -121.65, north: 37.05 },
  { name: 'san_francisco_bay_delta', west: -122.65, south: 37.25, east: -121.55, north: 38.25 },
  { name: 'puget_sound', west: -123.25, south: 47.0, east: -122.0, north: 48.5 },
  { name: 'chesapeake_bay', west: -77.6, south: 36.8, east: -75.6, north: 39.7 },
  { name: 'new_york_harbor_long_island_sound', west: -74.35, south: 40.35, east: -72.7, north: 41.35 },
];

const BOAT_RENDER_LAND_EXCLUSION_BOXES = [
  { name: 'los_angeles_orange_county_mainland_boat_exclusion', west: -118.72, south: 33.48, east: -117.50, north: 34.42 },
  { name: 'san_diego_county_mainland_boat_exclusion', west: -117.36, south: 32.45, east: -116.65, north: 33.60 },
  { name: 'ventura_santa_barbara_mainland_boat_exclusion', west: -120.18, south: 34.22, east: -118.55, north: 35.08 },
  { name: 'socal_inland_mountains_boat_exclusion', west: -119.75, south: 34.05, east: -116.65, north: 36.45 },
  { name: 'san_clemente_island_land', west: -118.68, south: 32.75, east: -118.25, north: 33.10 },
  { name: 'santa_catalina_island_land', west: -118.65, south: 33.25, east: -118.25, north: 33.55 },
  { name: 'san_nicolas_island_land', west: -119.62, south: 33.12, east: -119.35, north: 33.34 },
  { name: 'santa_cruz_santa_rosa_islands_land', west: -120.32, south: 33.85, east: -119.45, north: 34.12 },
  { name: 'anacapa_santa_barbara_islands_land', west: -119.52, south: 33.43, east: -119.15, north: 34.05 },
  { name: 'central_california_mainland_boat_exclusion', west: -122.55, south: 34.55, east: -120.05, north: 37.35 },
  { name: 'bay_area_mainland_boat_exclusion', west: -122.75, south: 37.05, east: -121.55, north: 38.45 },
  { name: 'oregon_washington_coastal_mainland_boat_exclusion', west: -124.35, south: 42.0, east: -122.0, north: 47.05 },
  { name: 'puget_lowlands_boat_exclusion', west: -123.35, south: 47.0, east: -121.6, north: 48.7 },
  { name: 'florida_peninsula_boat_exclusion', west: -82.85, south: 25.1, east: -80.05, north: 30.35 },
  { name: 'texas_louisiana_coastal_land_boat_exclusion', west: -97.8, south: 28.0, east: -90.0, north: 31.0 },
  { name: 'mid_atlantic_coastal_land_boat_exclusion', west: -78.2, south: 35.5, east: -73.4, north: 41.2 },
  { name: 'new_england_coastal_land_boat_exclusion', west: -72.2, south: 41.2, east: -69.5, north: 44.8 },
];

function inBox(lat: number, lon: number, box: { west: number; south: number; east: number; north: number }): boolean {
  return lon >= box.west && lon <= box.east && lat >= box.south && lat <= box.north;
}

function payloadSaysBoatWater(boat: BoatEntity): boolean {
  const meta = (boat as unknown as { safety_metadata?: { water_safe?: unknown; boat_mask_checked?: unknown; marine_mask?: { should_render_boat?: unknown; should_render_ocean?: unknown } } }).safety_metadata;
  if (!meta) return true;
  if (meta.boat_mask_checked === true && meta.marine_mask?.should_render_boat === false) return false;
  if (meta.water_safe === false) return false;
  return true;
}

function frontendBoatPointAllowed(lat: number, lon: number): boolean {
  if (BOAT_HARBOR_ALLOW_BOXES.some((box) => inBox(lat, lon, box))) return true;
  return !BOAT_RENDER_LAND_EXCLUSION_BOXES.some((box) => inBox(lat, lon, box));
}

function boatEntityPassesLandMask(boat: BoatEntity): boolean {
  return payloadSaysBoatWater(boat) && frontendBoatPointAllowed(boat.lat, boat.lon);
}

function headingFromUV(u: number, v: number, fallback = 0): number {
  if (Math.hypot(u, v) < 0.01) return fallback;
  // heading clockwise from north. u=east, v=north.
  return ((Math.atan2(u, v) * 180) / Math.PI + 360) % 360;
}

function nearestSample(lat: number, lon: number, samples: FieldSample[]): FieldSample | undefined {
  let best: { sample: FieldSample; d2: number } | undefined;
  for (const sample of samples) {
    const dLat = sample.lat - lat;
    const dLon = sample.lon - lon;
    const d2 = dLat * dLat + dLon * dLon;
    if (!best || d2 < best.d2) best = { sample, d2 };
  }
  return best?.sample;
}

export function buildMergedBoatFeatures(boats: BoatEntity[], oceanSamples: FieldSample[], maxCount = 24): BoatRenderFeature[] {
  return boats.filter(boatEntityPassesLandMask).slice(0, maxCount).map((boat, index) => {
    const nearest = nearestSample(boat.lat, boat.lon, oceanSamples);
    const currentU = finite((boat as unknown as Record<string, unknown>).current_u, finite(nearest?.values.current_u, 0));
    const currentV = finite((boat as unknown as Record<string, unknown>).current_v, finite(nearest?.values.current_v, 0));
    const currentMps = finite(nearest?.values.current_speed, Math.hypot(currentU, currentV));
    const currentKt = currentMps * 1.94384;
    const rawHeading = finite((boat as unknown as Record<string, unknown>).heading_deg, NaN);
    const headingDeg = Number.isFinite(rawHeading) ? rawHeading : headingFromUV(currentU, currentV, index * 37);
    const safety = normalizeSafety((boat as unknown as Record<string, unknown>).safety);
    const model = String((boat as unknown as Record<string, unknown>).model ?? 'ship2.gltf');
    const sst = finite(nearest?.values.sst_c, NaN);
    return {
      id: boat.id,
      lat: boat.lat,
      lon: boat.lon,
      headingDeg,
      currentU,
      currentV,
      currentKt,
      safety,
      model,
      title: `${boat.id} · ${safety} · heading ${headingDeg.toFixed(0)}° · current ${currentKt.toFixed(2)} kt${Number.isFinite(sst) ? ` · SST ${sst.toFixed(1)}°C` : ''} · strict boat land-mask · merged old marker/new ocean truth`,
    };
  });
}

function safetyFill(boat: BoatRenderFeature, alpha: number): string {
  if (boat.safety === 'rough') return `rgba(248,113,113,${alpha})`;
  if (boat.safety === 'caution') return `rgba(250,204,21,${alpha})`;
  if (boat.safety === 'good') return `rgba(125,211,252,${alpha})`;
  return `rgba(203,213,225,${alpha})`;
}

function safetyStroke(boat: BoatRenderFeature, alpha: number): string {
  if (boat.safety === 'rough') return `rgba(254,202,202,${alpha})`;
  if (boat.safety === 'caution') return `rgba(254,240,138,${alpha})`;
  if (boat.safety === 'good') return `rgba(186,230,253,${alpha})`;
  return `rgba(226,232,240,${alpha})`;
}

export function boatLegacyPolygons(boats: BoatRenderFeature[]): PolygonSpec[] {
  const polygons: PolygonSpec[] = [];
  for (const [index, boat] of boats.entries()) {
    const speedBoost = Math.min(1, boat.currentKt / 2.5);
    polygons.push({
      ...polygonSpec(
        `boat-merged:${boat.id}:safety-halo`,
        ellipsePath({
          lat: boat.lat,
          lon: boat.lon,
          altitudeM: 56,
          radiusXM: 360 + speedBoost * 420,
          radiusYM: 180 + speedBoost * 230,
          rotationRad: ((90 - boat.headingDeg) * Math.PI) / 180,
          segments: 18,
          scallop: 0.025,
          seed: index * 0.41,
        }),
        safetyFill(boat, 0.12 + speedBoost * 0.10),
        safetyStroke(boat, 0.38),
        0.9,
        boat.title,
      ),
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 50 + index,
    });

    polygons.push({
      ...polygonSpec(
        `boat-merged:${boat.id}:hull`,
        trianglePath(boat.lat, boat.lon, 185, 980 + speedBoost * 290, 420 + speedBoost * 120, boat.headingDeg),
        safetyFill(boat, 0.70),
        'rgba(248,250,252,.88)',
        1.8,
        boat.title,
      ),
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 64 + index,
    });

    polygons.push({
      ...polygonSpec(
        `boat-merged:${boat.id}:bow-glass`,
        trianglePath(boat.lat, boat.lon, 205, 430 + speedBoost * 130, 160, boat.headingDeg),
        'rgba(255,255,255,.34)',
        'rgba(255,255,255,.58)',
        0.7,
        `${boat.title} · bow-forward`,
      ),
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 74 + index,
    });
  }
  return polygons;
}

export function boatLegacyWakeLines(boats: BoatRenderFeature[]): PolylineSpec[] {
  const lines: PolylineSpec[] = [];
  for (const [index, boat] of boats.entries()) {
    const rad = ((90 - boat.headingDeg) * Math.PI) / 180;
    const backLat = -Math.sin(rad) * 0.0065;
    const backLon = -Math.cos(rad) * 0.0065;
    const spreadLat = Math.cos(rad) * 0.0019;
    const spreadLon = -Math.sin(rad) * 0.0019;
    const currentLat = boat.currentV * 0.006;
    const currentLon = boat.currentU * 0.006;
    for (const side of [-1, 1]) {
      lines.push({
        id: `boat-merged:${boat.id}:wake:${side}:${index}`,
        path: [
          { lat: boat.lat - backLat * 0.10, lng: boat.lon - backLon * 0.10, altitude: 48 },
          { lat: boat.lat + backLat + spreadLat * side + currentLat, lng: boat.lon + backLon + spreadLon * side + currentLon, altitude: 34 },
        ],
        strokeColor: 'rgba(224,242,254,.62)',
        outerColor: safetyFill(boat, 0.22),
        strokeWidth: 1.1 + Math.min(3.5, boat.currentKt * 0.8),
        altitudeMode: 'RELATIVE_TO_GROUND',
      });
    }
  }
  return lines;
}

export function boatLegacyMarkers(boats: BoatRenderFeature[]): MarkerSpec[] {
  return boats.map((boat) => ({
    id: `boat-current-label:${boat.id}`,
    lat: boat.lat,
    lon: boat.lon,
    altitude: 520,
    label: `${boat.currentKt.toFixed(1)} kt`,
    title: `${boat.title} · overhead current-speed label`,
    className: `legacy-boat-marker boat-current-text legacy-boat-${boat.safety}`,
    color: boat.safety === 'rough' ? '#fecaca' : boat.safety === 'caution' ? '#fef08a' : boat.safety === 'good' ? '#bae6fd' : '#e2e8f0',
    glowColor: boat.safety === 'rough' ? 'rgba(248,113,113,.90)' : boat.safety === 'caution' ? 'rgba(250,204,21,.86)' : 'rgba(125,211,252,.82)',
    scale: 0.95 + Math.min(0.75, boat.currentKt * 0.20),
    opacity: 0.96,
  }));
}

function modelScaleForSpan(viewportSpanDeg = 2): number {
  if (viewportSpanDeg > 8) return 34;
  if (viewportSpanDeg > 4) return 20;
  if (viewportSpanDeg > 1.5) return 12;
  if (viewportSpanDeg > 0.5) return 7;
  if (viewportSpanDeg > 0.16) return 3.6;
  return 1.25;
}

export function boatShipModels(boats: BoatRenderFeature[], viewportSpanDeg = 2): ModelSpec[] {
  const scale = modelScaleForSpan(viewportSpanDeg);
  return boats.map((boat) => ({
    id: `ship2-model:${boat.id}`,
    lat: boat.lat,
    lon: boat.lon,
    altitude: 42,
    src: SHIP2_MODEL_SRC,
    // ship2.gltf measures about 14.8 model units long, almost exactly 50 ft if units are meters.
    // Scale is intentionally viewport-visible while preserving a 50 ft source model contract.
    scale,
    heading: boat.headingDeg,
    tilt: 0,
    roll: 0,
    altitudeMode: 'RELATIVE_TO_GROUND',
    title: `${boat.title} · 50 ft ship2.gltf source model · viewport scale ${scale.toFixed(1)}x`,
  }));
}

export function boatOceanHazardPolygons(samples: FieldSample[], maxCount = 90): PolygonSpec[] {
  const polygons: PolygonSpec[] = [];
  const ranked = samples.map((sample): BoatHazardFeature => {
    const u = finite(sample.values.current_u ?? sample.values.u ?? sample.values.water_u, 0);
    const v = finite(sample.values.current_v ?? sample.values.v ?? sample.values.water_v, 0);
    const speedMps = finite(sample.values.current_speed, Math.hypot(u, v));
    const currentKt = speedMps * 1.94384;
    const baitScore = finite(sample.values.bait_score ?? sample.values.bait_probability, 0);
    const depthM = finite(sample.values.depth_m ?? sample.values.bait_depth_m, 0);
    const shallowRisk = depthM > 0 ? Math.max(0, 1 - depthM / 35) : 0;
    const risk = Math.max(0, Math.min(1, currentKt / 2.8 * 0.55 + baitScore * 0.22 + shallowRisk * 0.35));
    return { id: sample.id, lat: sample.lat, lon: sample.lon, currentKt, baitScore, depthM, risk };
  }).filter((hazard) => hazard.risk > 0.18 || hazard.currentKt > 0.28)
    .sort((a, b) => b.risk - a.risk)
    .slice(0, maxCount);

  for (const [index, hazard] of ranked.entries()) {
    const rough = hazard.risk > 0.66;
    const caution = hazard.risk > 0.40;
    const fill = rough ? `rgba(248,113,113,${(0.10 + hazard.risk * 0.20).toFixed(3)})` : caution ? `rgba(250,204,21,${(0.08 + hazard.risk * 0.17).toFixed(3)})` : `rgba(56,189,248,${(0.055 + hazard.risk * 0.10).toFixed(3)})`;
    const stroke = rough ? 'rgba(254,202,202,.44)' : caution ? 'rgba(254,240,138,.40)' : 'rgba(186,230,253,.30)';
    polygons.push({
      ...polygonSpec(
        `boat-ocean-hazard:${hazard.id}`,
        ellipsePath({
          lat: hazard.lat,
          lon: hazard.lon,
          altitudeM: 24 + Math.min(90, hazard.risk * 115),
          radiusXM: 1050 + hazard.risk * 2150,
          radiusYM: 640 + hazard.risk * 1250,
          rotationRad: index * 0.37,
          segments: 18,
          scallop: 0.035,
          seed: index * 0.91,
        }),
        fill,
        stroke,
        0.55 + hazard.risk * 1.15,
        `ocean hazard · current ${hazard.currentKt.toFixed(2)} kt · bait ${Math.round(hazard.baitScore * 100)}% · depth ${hazard.depthM.toFixed(0)} m · risk ${Math.round(hazard.risk * 100)}%`,
      ),
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 18 + index,
    });
  }
  return polygons;
}

export function boatLegacySummary(boats: BoatRenderFeature[]): string {
  const rough = boats.filter((boat) => boat.safety === 'rough').length;
  const caution = boats.filter((boat) => boat.safety === 'caution').length;
  const topCurrent = boats.reduce((max, boat) => Math.max(max, boat.currentKt), 0);
  return `Boat renderer merge: ${boats.length} ship2.gltf 50 ft models + current-speed labels using ocean truth; rough ${rough}, caution ${caution}, max current ${topCurrent.toFixed(2)} kt`;
}
