import './styles/app.css';
import { fetchSceneFrame, fetchViewportSpatial } from './api/client';
import { openFieldStream } from './api/stream';
import { FieldStore } from './fields/fieldStore';
import { samplePatchGrid, type FieldSample } from './fields/sampler';
import { createGoogle3DMap, waterbodyPolygons, type MarkerSpec, type PolylineSpec, type PolygonSpec } from './renderer/google3d';
import { ellipsePath, polygonSpec, trianglePath, zigzagLine } from './renderer/geometryPrimitives';
import { buildCloudBodyRender, type CloudFeaturesPayload, type CloudTier } from './renderer/cloudParticles';
import { CloudMorphController } from './renderer/cloudMorph';
import { type OceanFeaturePayload } from './renderer/baitLegacyVisual';
import { BaitSchoolMorphController } from './renderer/baitSchoolMorph';
import { boatLegacyMarkers, boatLegacyPolygons, boatLegacySummary, boatLegacyWakeLines, boatOceanHazardPolygons, boatShipModels, buildMergedBoatFeatures } from './renderer/boatLegacyVisual';
import { ViewportController } from './renderer/viewportController';
import type { BBox, FieldPatch } from './types/field';
import type { BoatEntity, LightningFlash } from './types/layers';
import type { ReportPoint, SpatialFeature } from './types/spatial';
import { renderLayerPills, type LayerId } from './ui/layerPills';
import { createIntelligencePane, type LocationIntelContext, type SharkIntelSelection } from './ui/intelligencePane';

const app = document.querySelector<HTMLDivElement>('#app')!;
const shell = document.createElement('main');
shell.className = 'app-shell';
app.appendChild(shell);

const title = document.createElement('div');
title.className = 'glass-title';
title.innerHTML = '<b>LFTR Marine Intelligence Globe</b><small>Google Photorealistic 3D</small>';
const pane = createIntelligencePane();
const fields = new FieldStore();
const viewport = new ViewportController();
const activeLayers = new Set<LayerId>(['locations', 'clouds', 'rain', 'bait', 'boats', 'shark-intel', 'inland-water', 'lightning']);

const DEFAULT_SOCAL_BBOX: BBox = { west: -125, south: 32, east: -117, north: 38 };

function bboxToParam(bbox: BBox): string {
  return [bbox.west, bbox.south, bbox.east, bbox.north].join(',');
}

function stableBBoxKey(bbox: BBox): string {
  return [bbox.west, bbox.south, bbox.east, bbox.north].map((v) => v.toFixed(3)).join(',');
}

function marker(id: string, lat: number, lon: number, label: string, title: string, altitude = 100, extras: Partial<MarkerSpec> = {}): MarkerSpec {
  return { id, lat, lon, label, title, altitude, ...extras };
}

function directionGlyph(u: number, v: number): string {
  const angle = Math.atan2(v, u);
  if (!Number.isFinite(angle)) return '→';
  const glyphs = ['→', '↗', '↑', '↖', '←', '↙', '↓', '↘'];
  const index = Math.round((((angle + Math.PI * 2) % (Math.PI * 2)) / (Math.PI * 2)) * 8) % 8;
  return glyphs[index];
}


type CloudFamily = 'cumulus' | 'stratus' | 'cirrus' | 'marine-stratus' | 'cumulonimbus';
type CloudSize = 'micro' | 'small' | 'medium' | 'large' | 'massive';
type CloudRenderStyle = 'puff-cluster' | 'flat-sheet' | 'wispy-streak' | 'coastal-blanket' | 'tower-stack';

type SamplePoint = FieldSample;

interface CloudMarkerStyle {
  family: CloudFamily;
  renderStyle: CloudRenderStyle;
  size: CloudSize;
  altitude: number;
  scale: number;
  opacity: number;
  color: string;
  glowColor: string;
  label: string;
  title: string;
}

type OceanFeaturesPayload = OceanFeaturePayload & {
  grid_shape?: [number, number];
  depth_levels?: string[];
};

function distanceKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const earthKm = 6371;
  const dLat = (bLat - aLat) * Math.PI / 180;
  const dLon = (bLon - aLon) * Math.PI / 180;
  const lat1 = aLat * Math.PI / 180;
  const lat2 = bLat * Math.PI / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * earthKm * Math.asin(Math.min(1, Math.sqrt(h)));
}

function nearestSample(samples: SamplePoint[], lat: number, lon: number): (SamplePoint & { distanceKm: number }) | null {
  let best: (SamplePoint & { distanceKm: number }) | null = null;
  for (const sample of samples) {
    const d = distanceKm(lat, lon, sample.lat, sample.lon);
    if (!best || d < best.distanceKm) best = { ...sample, distanceKm: d };
  }
  return best;
}

function nearestFeature(features: SpatialFeature[], lat: number, lon: number): (SpatialFeature & { distanceKm: number }) | null {
  let best: (SpatialFeature & { distanceKm: number }) | null = null;
  for (const feature of features) {
    const point = feature.label_point ?? { lat: feature.latitude ?? NaN, lon: feature.longitude ?? NaN };
    if (!Number.isFinite(point.lat) || !Number.isFinite(point.lon)) continue;
    const d = distanceKm(lat, lon, point.lat, point.lon);
    if (!best || d < best.distanceKm) best = { ...feature, distanceKm: d };
  }
  return best;
}

function compassFromVector(u: number, v: number): string {
  if (!Number.isFinite(u) || !Number.isFinite(v) || Math.hypot(u, v) <= 0.0001) return 'slack/variable';
  const deg = (Math.atan2(u, v) * 180 / Math.PI + 360) % 360;
  const dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  return `${dirs[Math.round(deg / 22.5) % 16]} ${Math.round(deg)}°`;
}

function patchValidTime(patch: FieldPatch | undefined): string | undefined {
  const value = patch?.payload?.valid_time;
  return typeof value === 'string' ? value : undefined;
}

function valueFrom(sample: { values: Record<string, number> }, names: string[], fallback = 0): number {
  for (const name of names) {
    const value = sample.values[name];
    if (Number.isFinite(value)) return value;
  }
  return fallback;
}

function cloudSizeFrom(density: number): CloudSize {
  if (density < 0.18) return 'micro';
  if (density < 0.34) return 'small';
  if (density < 0.55) return 'medium';
  if (density < 0.78) return 'large';
  return 'massive';
}

function renderStyleForCloudFamily(family: CloudFamily): CloudRenderStyle {
  if (family === 'cirrus') return 'wispy-streak';
  if (family === 'stratus') return 'flat-sheet';
  if (family === 'marine-stratus') return 'coastal-blanket';
  if (family === 'cumulonimbus') return 'tower-stack';
  return 'puff-cluster';
}

function cloudFamilyLabel(family: CloudFamily): string {
  // These glyphs are deliberately simple ellipsoid/streak primitives.  They are
  // visible even when a Google 3D marker implementation ignores custom DOM.
  if (family === 'cirrus') return '━';
  if (family === 'stratus' || family === 'marine-stratus') return '▬';
  return '●';
}

function cloudFamilyColor(family: CloudFamily, density = 0.55, rain = 0): string {
  if (family === 'cumulonimbus') {
    const tone = Math.max(80, Math.min(205, Math.round(220 - density * 82 - rain * 58)));
    return `rgb(${tone},${tone + 4},${tone + 10})`;
  }
  if (family === 'marine-stratus') return 'rgb(213,224,231)';
  if (family === 'stratus') return 'rgb(226,233,238)';
  if (family === 'cirrus') return 'rgb(248,252,255)';
  return 'rgb(255,255,255)';
}

function cloudFamilyGlow(family: CloudFamily, rain = 0): string {
  if (family === 'cumulonimbus') return `rgba(82,92,112,${0.52 + Math.min(0.25, rain * 0.28)})`;
  if (family === 'marine-stratus') return 'rgba(205,222,232,.54)';
  if (family === 'stratus') return 'rgba(225,235,242,.48)';
  if (family === 'cirrus') return 'rgba(246,252,255,.30)';
  return 'rgba(255,255,255,.62)';
}

function classifyCloudFamily(density: number, low: number, mid: number, high: number, rain: number, humidity: number): CloudFamily {
  if (rain > 0.44 || (density > 0.82 && humidity > 0.54)) return 'cumulonimbus';
  if (low > 0.46 && humidity > 0.48 && density > 0.25) return 'marine-stratus';
  if (high > low && high > mid && density < 0.64 && rain < 0.22) return 'cirrus';
  if (low > 0.38 || density > 0.58) return 'stratus';
  return 'cumulus';
}

function classifyCloud(sample: { values: Record<string, number> }): CloudMarkerStyle | null {
  const density = Math.max(0, Math.min(1, valueFrom(sample, ['cloud_density', 'total_cloud_cover', 'cloud_total'])));
  const rain = Math.max(0, Math.min(1, valueFrom(sample, ['rain_rate', 'precipitation_rate'])));
  const low = Math.max(0, Math.min(1, valueFrom(sample, ['low_cloud', 'low_cloud_cover', 'cloud_low'], density * 0.45)));
  const mid = Math.max(0, Math.min(1, valueFrom(sample, ['mid_cloud', 'medium_cloud_cover', 'cloud_mid'], density * 0.35)));
  const high = Math.max(0, Math.min(1, valueFrom(sample, ['high_cloud', 'high_cloud_cover', 'cloud_high'], density * 0.2)));
  const humidity = Math.max(0, Math.min(1.2, valueFrom(sample, ['humidity', 'relative_humidity'], 0.55)));

  if (density < 0.16 && high < 0.2) return null;

  const family = classifyCloudFamily(density, low, mid, high, rain, humidity);
  const renderStyle = renderStyleForCloudFamily(family);
  const size = cloudSizeFrom(Math.max(density, low, mid, high, rain));
  const altitudeByFamily: Record<CloudFamily, number> = {
    'marine-stratus': 650 + density * 1200,
    stratus: 1300 + density * 3100,
    cumulus: 2400 + density * 5600,
    cirrus: 7800 + high * 5400,
    cumulonimbus: 3200 + density * 11200,
  };
  const scaleBySize: Record<CloudSize, number> = { micro: 0.62, small: 0.92, medium: 1.28, large: 1.85, massive: 2.48 };
  const opacity = Math.min(0.92, Math.max(0.16, 0.18 + density * 0.56 + rain * 0.22));
  return {
    family,
    renderStyle,
    size,
    altitude: altitudeByFamily[family],
    scale: scaleBySize[size] * (family === 'cirrus' ? 1.35 : 1) * (family === 'cumulonimbus' ? 1.16 : 1),
    opacity,
    color: cloudFamilyColor(family, density, rain),
    glowColor: cloudFamilyGlow(family, rain),
    label: cloudFamilyLabel(family),
    title: `${family} ${size} · ${renderStyle} · cloud ${Math.round(density * 100)}% · rain ${rain.toFixed(2)}`,
  };
}

function cloudFamilyMarkers(patch: FieldPatch | undefined): MarkerSpec[] {
  // Marker fallback retained for emergency debugging only.  The active cloud path
  // below uses gmp-polygon-3d so clouds do not reduce to white marker spheres.
  void patch;
  return [];
}

function cloudFamilyPolygons(patch: FieldPatch | undefined): PolygonSpec[] {
  const polygons: PolygonSpec[] = [];
  const samples = samplePatchGrid(patch, 56) as SamplePoint[];
  for (const sample of samples) {
    const style = classifyCloud(sample);
    if (!style) continue;
    const windU = valueFrom(sample, ['wind_u'], 0);
    const windV = valueFrom(sample, ['wind_v'], 0);
    const driftLon = Math.max(-0.035, Math.min(0.035, windU * 0.006));
    const driftLat = Math.max(-0.035, Math.min(0.035, windV * 0.006));
    const rotation = Math.atan2(windV || 0.2, windU || 0.6);
    const density = Math.max(0, Math.min(1, valueFrom(sample, ['cloud_density', 'total_cloud_cover', 'cloud_total'], 0.45)));
    const rxM = style.renderStyle === 'wispy-streak' ? 5400 : style.renderStyle === 'coastal-blanket' ? 4200 : style.renderStyle === 'flat-sheet' ? 3600 : style.renderStyle === 'tower-stack' ? 1800 : 2400;
    const ryM = style.renderStyle === 'wispy-streak' ? 520 : style.renderStyle === 'coastal-blanket' ? 1050 : style.renderStyle === 'flat-sheet' ? 1250 : style.renderStyle === 'tower-stack' ? 1650 : 1800;
    const tone = style.family === 'cumulonimbus' ? Math.round(130 + density * 52) : style.family === 'cirrus' ? 244 : style.family === 'marine-stratus' ? 210 : 224;
    const spec = polygonSpec(
      `field-cloud-poly:${style.family}:${style.size}:${sample.id}`,
      ellipsePath({
        lat: sample.lat + driftLat,
        lon: sample.lon + driftLon,
        altitudeM: style.altitude,
        radiusXM: rxM * style.scale,
        radiusYM: ryM * style.scale,
        rotationRad: rotation,
        segments: style.renderStyle === 'wispy-streak' ? 18 : 22,
        scallop: style.family === 'cumulus' || style.family === 'cumulonimbus' ? 0.065 : 0.02,
      }),
      `rgba(${tone},${tone},${Math.min(255, tone + 10)},${Math.min(0.42, style.opacity * 0.55).toFixed(3)})`,
      `rgba(255,255,255,${Math.min(0.28, style.opacity * 0.24).toFixed(3)})`,
      style.family === 'cumulonimbus' ? 1.2 : 0.8,
      style.title,
    );
    spec.advectU = windU;
    spec.advectV = windV;
    polygons.push(spec);
  }
  return polygons;
}



function cloudFeatureMarkers(payload: CloudFeaturesPayload | null, tier: CloudTier = 'regional'): MarkerSpec[] {
  // Marker fallback retained for emergency/manual comparison only.  The main
  // renderer intentionally does not call syncMarkers('clouds', ...) anymore.
  void payload;
  void tier;
  return [];
}

function cloudFeaturePolygons(payload: CloudFeaturesPayload | null, tier: CloudTier = 'regional'): PolygonSpec[] {
  return buildCloudBodyRender(payload, tier).polygons;
}

function locationOrbScaleForBBox(bbox: BBox | null): number {
  if (!bbox) return 1.18;
  const span = Math.max(Math.abs(bbox.east - bbox.west), Math.abs(bbox.north - bbox.south));
  if (!Number.isFinite(span) || span <= 0) return 1.18;
  // Smaller viewport span means the user is zoomed in. Grow fish/location
  // cylinders aggressively at local zoom now that they are true gmp-polygon-3d
  // extrusions, while still keeping regional/global views readable.
  if (span <= 0.20) return 4.45;
  if (span <= 0.35) return 3.95;
  if (span <= 0.75) return 3.25;
  if (span <= 1.5) return 2.55;
  if (span <= 3.0) return 1.95;
  if (span <= 7.0) return 1.45;
  return 1.18;
}

function locationOrbPolygons(reports: ReportPoint[], onSelect: (report: ReportPoint) => void, scale = 1): PolygonSpec[] {
  // Native Google 3D cylinders: an elevated circle with extruded=true creates
  // real gmp-polygon-3d side walls down to terrain. There is no native polygon
  // height property, so each path altitude is the top height of that cylinder.
  // Stacking several translucent cylinders gives the old green-orb glow while
  // staying in true map-space geometry instead of GLB/model or marker fallback.
  return reports.slice(0, 120).flatMap((report, index) => {
    const clampedScale = Math.max(1.0, Math.min(4.6, scale));
    const baseRadius = (225 + (index % 4) * 22) * clampedScale;
    const baseAltitude = (430 + (index % 5) * 22) * Math.min(2.65, clampedScale);
    const layers = [
      {
        suffix: 'ground-glow',
        altitudeM: 82,
        radiusM: baseRadius * 3.35,
        fill: 'rgba(0,255,85,.18)',
        stroke: 'rgba(120,255,175,.46)',
        strokeWidth: 1.15,
        extruded: false,
        zIndex: 38,
      },
      {
        suffix: 'outer-cylinder',
        altitudeM: baseAltitude + 520,
        radiusM: baseRadius * 1.62,
        fill: 'rgba(0,255,85,.38)',
        stroke: 'rgba(120,255,175,.72)',
        strokeWidth: 1.65,
        extruded: true,
        zIndex: 42,
      },
      {
        suffix: 'core-cylinder',
        altitudeM: baseAltitude + 760,
        radiusM: baseRadius * 1.05,
        fill: 'rgba(0,255,85,.72)',
        stroke: 'rgba(222,255,232,.96)',
        strokeWidth: 2.25,
        extruded: true,
        zIndex: 46,
        click: true,
      },
      {
        suffix: 'upper-cap',
        altitudeM: baseAltitude + 1040,
        radiusM: baseRadius * 0.68,
        fill: 'rgba(140,255,180,.82)',
        stroke: 'rgba(250,255,252,.96)',
        strokeWidth: 1.45,
        extruded: true,
        zIndex: 50,
      },
      {
        suffix: 'white-spark',
        altitudeM: baseAltitude + 1220,
        radiusM: baseRadius * 0.32,
        fill: 'rgba(240,255,244,.92)',
        stroke: 'rgba(255,255,255,1)',
        strokeWidth: 1.05,
        extruded: false,
        zIndex: 54,
      },
    ];

    return layers.map((layer) => ({
      ...polygonSpec(
        `location-orb-cylinder:${report.id}:${layer.suffix}`,
        ellipsePath({
          lat: report.latitude,
          lon: report.longitude,
          altitudeM: layer.altitudeM,
          radiusXM: layer.radiusM,
          radiusYM: layer.radiusM,
          rotationRad: 0,
          segments: 32,
          scallop: layer.suffix === 'core-cylinder' ? 0.012 : 0,
          seed: index * 0.71,
        }),
        layer.fill,
        layer.stroke,
        layer.strokeWidth,
        report.title,
      ),
      extruded: layer.extruded,
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: layer.zIndex,
      onClick: layer.click ? () => onSelect(report) : undefined,
    }));
  });
}


function locationOrbMarkers(reports: ReportPoint[], onSelect: (report: ReportPoint) => void, scale = 1): MarkerSpec[] {
  // A true gmp-marker-3d-interactive is kept above the 3D cylinder stack so the
  // fish-location orbs stay clickable in browsers where polygon hit-testing is spotty.
  return reports.slice(0, 120).map((report, index) => {
    const clampedScale = Math.max(1.0, Math.min(4.6, scale));
    const altitude = (1550 + (index % 5) * 54) * Math.min(2.25, clampedScale);
    const title = `${report.title}\n${report.latitude.toFixed(5)}, ${report.longitude.toFixed(5)}\n${report.summary ?? ''}`;
    return marker(
      `location-hit:${report.id}`,
      report.latitude,
      report.longitude,
      '●',
      title,
      altitude,
      {
        className: 'location-orb-marker old-green-orb-marker location-hit-target',
        template: 'green-orb',
        probability: 1,
        scale: Math.max(1.1, Math.min(2.65, 0.95 + clampedScale * 0.30)),
        onClick: () => onSelect(report),
      },
    );
  });
}

function reportText(report: ReportPoint): string {
  return `${report.title} ${report.summary} ${Object.values(report.csv_fields ?? {}).join(' ')}`.toLowerCase();
}

function sharkScoreFromReport(report: ReportPoint): number {
  const text = reportText(report);
  let score = 0;
  for (const term of ['shark', 'leopard shark', 'thresher', 'tiger', 'batray', 'bat ray', 'ray', 'stingray', 'big bite', 'teeth']) {
    if (text.includes(term)) score += term.includes('shark') || term === 'thresher' ? 0.28 : 0.14;
  }
  return Math.max(0, Math.min(1, score));
}


function reportAllowsMarineIntel(report: ReportPoint): boolean {
  return report.marine_mask?.should_render_ocean !== false;
}

function oceanSharkScore(sample: SamplePoint): number {
  const bait = Math.max(0, Math.min(1, valueFrom(sample, ['bait_score'], 0)));
  const current = Math.min(1, Math.hypot(valueFrom(sample, ['current_u'], 0), valueFrom(sample, ['current_v'], 0)) / 1.8);
  const tempC = valueFrom(sample, ['sst_c', 'water_temp_c', 'temperature'], NaN);
  const tempBand = Number.isFinite(tempC) ? Math.max(0, 1 - Math.abs(tempC - 17.5) / 7.5) : 0.35;
  return Math.max(0, Math.min(1, bait * 0.58 + current * 0.24 + tempBand * 0.18));
}


function sharkReportIntel(report: ReportPoint): SharkIntelSelection {
  const score = sharkScoreFromReport(report);
  const coordinate = `${report.latitude.toFixed(5)}, ${report.longitude.toFixed(5)}`;
  return {
    title: `${report.title} · Shark report`,
    lat: report.latitude,
    lon: report.longitude,
    score,
    source: `CSV shark mention · ${report.source}`,
    summary: report.summary || 'CSV location contains shark/ray/big-bite language; use local ocean conditions to confirm before interpreting as active presence.',
    evidence: [
      ['prediction_basis', 'CSV report text keyword score'],
      ['keyword_score', score.toFixed(2)],
      ['coordinates', coordinate],
      ['observed_at', report.observed_at || 'unknown'],
      ['marine_mask', report.marine_mask?.classification || 'water_or_allowed_coastal'],
      ...Object.entries(report.csv_fields ?? {}).slice(0, 10),
    ],
  };
}

function sharkOceanIntel(sample: SamplePoint): SharkIntelSelection {
  const score = oceanSharkScore(sample);
  const bait = valueFrom(sample, ['bait_score'], 0);
  const currentU = valueFrom(sample, ['current_u'], 0);
  const currentV = valueFrom(sample, ['current_v'], 0);
  const current = Math.hypot(currentU, currentV);
  const tempC = valueFrom(sample, ['sst_c', 'water_temp_c', 'temperature'], NaN);
  const tempText = Number.isFinite(tempC) ? `${tempC.toFixed(1)} °C / ${(tempC * 9 / 5 + 32).toFixed(1)} °F` : 'unknown';
  const summary = score > 0.72
    ? 'Higher shark-intel probability from strong bait score, usable current, and favorable surface temperature band.'
    : 'Moderate shark-intel area from ocean conditions. Treat this as a prediction marker, not a confirmed sighting.';
  return {
    title: 'Ocean shark-intel area',
    lat: sample.lat,
    lon: sample.lon,
    score,
    source: 'RTOFS/ocean truth prediction',
    summary,
    evidence: [
      ['prediction_basis', 'bait score + current + sea-surface temperature'],
      ['bait_score', bait.toFixed(2)],
      ['current_speed_proxy', current.toFixed(2)],
      ['current_u_v', `${currentU.toFixed(2)}, ${currentV.toFixed(2)}`],
      ['surface_temp', tempText],
      ['sample_id', sample.id],
    ],
  };
}

function sharkIntelPolygons(reports: ReportPoint[], oceanSamples: SamplePoint[]): PolygonSpec[] {
  const specs: PolygonSpec[] = [];
  for (const [index, report] of reports.entries()) {
    if (!reportAllowsMarineIntel(report)) continue;
    const score = sharkScoreFromReport(report);
    if (score <= 0.05) continue;
    const radius = 720 + score * 3200;
    specs.push({
      ...polygonSpec(
        `shark-report-ring:${report.id}`,
        ellipsePath({ lat: report.latitude, lon: report.longitude, altitudeM: 165 + score * 160, radiusXM: radius, radiusYM: radius * 0.62, rotationRad: index * 0.42, segments: 28, scallop: 0.025 }),
        `rgba(248,113,113,${(0.16 + score * 0.26).toFixed(3)})`,
        `rgba(254,202,202,${(0.42 + score * 0.30).toFixed(3)})`,
        1.4 + score * 1.2,
        `${report.title} · shark intel ${Math.round(score * 100)}%`,
      ),
      extruded: false,
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
    });
  }

  for (const sample of oceanSamples.filter((s) => oceanSharkScore(s) > 0.58).slice(0, 48)) {
    const score = oceanSharkScore(sample);
    const radius = 620 + score * 2300;
    specs.push({
      ...polygonSpec(
        `shark-ocean-intel:${sample.id}`,
        ellipsePath({ lat: sample.lat, lon: sample.lon, altitudeM: 105 + score * 95, radiusXM: radius * 1.35, radiusYM: radius * 0.58, rotationRad: score * 1.9, segments: 18, scallop: 0.04 }),
        `rgba(127,29,29,${(0.08 + score * 0.18).toFixed(3)})`,
        `rgba(251,113,133,${(0.24 + score * 0.30).toFixed(3)})`,
        0.9 + score * 1.2,
        `shark/ocean intel · bait/current/temp score ${score.toFixed(2)}`,
      ),
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
    });
  }
  return specs;
}

function sharkIntelMarkers(
  reports: ReportPoint[],
  oceanSamples: SamplePoint[],
  onSelect: (intel: SharkIntelSelection) => void,
): MarkerSpec[] {
  const reportMarkers = reports
    .filter((report) => reportAllowsMarineIntel(report) && sharkScoreFromReport(report) > 0.05)
    .slice(0, 36)
    .map((report) => {
      const intel = sharkReportIntel(report);
      return marker(
        `shark-hit:${report.id}`,
        report.latitude,
        report.longitude,
        '◆',
        `${report.title}\nShark intel from CSV\n${report.summary ?? ''}`,
        820,
        {
          className: 'shark-intel-marker shark-intel-hit-target',
          color: '#fecaca',
          glowColor: 'rgba(248,113,113,.92)',
          scale: 1.25 + intel.score * 0.9,
          onClick: () => onSelect(intel),
        },
      );
    });

  const oceanMarkers = oceanSamples
    .filter((sample) => oceanSharkScore(sample) > 0.58)
    .slice(0, 36)
    .map((sample, index) => {
      const intel = sharkOceanIntel(sample);
      return marker(
        `shark-ocean-hit:${sample.id}`,
        sample.lat,
        sample.lon,
        '◇',
        `Ocean shark-intel area\nPrediction ${Math.round(intel.score * 100)}%`,
        640 + (index % 4) * 42,
        {
          className: 'shark-intel-marker shark-ocean-intel-marker shark-intel-hit-target',
          color: '#fb7185',
          glowColor: 'rgba(251,113,133,.86)',
          scale: 1.05 + intel.score * 0.82,
          onClick: () => onSelect(intel),
        },
      );
    });

  return [...reportMarkers, ...oceanMarkers];
}

function baitPolygons(samples: SamplePoint[]): PolygonSpec[] {
  return samples
    .filter((sample) => (sample.values.bait_score ?? 0) > 0.34)
    .slice(0, 220)
    .map((sample) => {
      const score = sample.values.bait_score ?? 0;
      const hot = score > 0.76;
      return polygonSpec(
        `bait-poly:${sample.id}`,
        ellipsePath({ lat: sample.lat, lon: sample.lon, altitudeM: 70 + score * 95, radiusXM: 900 + score * 2600, radiusYM: 480 + score * 1400, rotationRad: score * 1.7, segments: 18, scallop: 0.055 }),
        hot ? `rgba(250,204,21,${(0.20 + score * 0.34).toFixed(3)})` : `rgba(45,212,191,${(0.18 + score * 0.34).toFixed(3)})`,
        hot ? 'rgba(254,240,138,.62)' : 'rgba(153,246,228,.56)',
        hot ? 1.5 : 1.1,
        `bait score ${score.toFixed(2)}`,
      );
    });
}

function rainIntensity(sample: SamplePoint): number {
  const raw = Math.max(0, valueFrom(sample, ['rain_rate', 'precipitation_rate', 'precip_rate'], 0));
  // Most LFTR field patches already normalize rain into roughly 0..1/2. If a
  // provider returns a larger precip rate, compress it without letting one storm
  // blank the whole viewport black.  The returned 0..1 value drives sphere count,
  // fall speed, color, and column height.
  return Math.max(0, Math.min(1, raw <= 2 ? raw / 1.25 : Math.log1p(raw) / 4));
}

function rainColorForIntensity(intensity: number, alpha = 0.88): string {
  const i = Math.max(0, Math.min(1, intensity));
  const steps = [
    { at: 0.05, rgb: [245, 250, 255] }, // mist / white
    { at: 0.22, rgb: [59, 130, 246] },  // blue
    { at: 0.40, rgb: [34, 197, 94] },   // green
    { at: 0.58, rgb: [250, 204, 21] },  // yellow
    { at: 0.74, rgb: [249, 115, 22] },  // orange
    { at: 0.90, rgb: [239, 68, 68] },   // red
    { at: 1.00, rgb: [15, 23, 42] },    // black core for violent cells
  ];
  const upper = steps.find((step) => i <= step.at) ?? steps[steps.length - 1];
  const lowerIndex = Math.max(0, steps.indexOf(upper) - 1);
  const lower = steps[lowerIndex];
  const span = Math.max(0.001, upper.at - lower.at);
  const t = Math.max(0, Math.min(1, (i - lower.at) / span));
  const rgb = upper.rgb.map((value, idx) => Math.round(lower.rgb[idx] + (value - lower.rgb[idx]) * t));
  return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`;
}

function rainCloudTopM(sample: SamplePoint, intensity: number): number {
  const density = Math.max(0, Math.min(1, valueFrom(sample, ['cloud_density', 'cloud_total', 'total_cloud'], 0)));
  const low = Math.max(0, Math.min(1, valueFrom(sample, ['low_cloud', 'cloud_low'], 0)));
  const mid = Math.max(0, Math.min(1, valueFrom(sample, ['mid_cloud', 'cloud_mid'], 0)));
  const high = Math.max(0, Math.min(1, valueFrom(sample, ['high_cloud', 'cloud_high'], 0)));
  // Zippy-style rain falls from the cloud roof, not from an arbitrary fixed height.
  // Use the cloud-family channels when available and let precip punch storms taller.
  const familyTop = 1250 + low * 2400 + mid * 5200 + high * 8600;
  const stormLift = intensity * (2200 + density * 4200);
  return Math.max(900, Math.min(14800, familyTop + stormLift));
}

function rainFootprintM(sample: SamplePoint, intensity: number, index: number): number {
  const density = Math.max(0, Math.min(1, valueFrom(sample, ['cloud_density', 'cloud_total', 'total_cloud'], 0)));
  const wobble = 0.86 + ((index % 5) * 0.055);
  return (520 + intensity * 2650 + density * 950) * wobble;
}

function rainSpherePolygons(sample: SamplePoint, intensity: number, id: string, lat: number, lon: number, altitudeM: number, radiusM: number, angle: number): PolygonSpec[] {
  // Google Maps 3D has polygons/markers/models, but no native sphere primitive.
  // A compact stack of translucent ellipse discs reads like a colored falling
  // sphere and keeps every piece in globe coordinates.
  const rings = [-0.82, -0.42, 0, 0.42, 0.82];
  const specs: PolygonSpec[] = [];
  for (const [ringIndex, z] of rings.entries()) {
    const f = Math.sqrt(Math.max(0.05, 1 - z * z));
    const alpha = (ringIndex === 2 ? 0.82 : 0.48) + intensity * 0.10;
    const spec = polygonSpec(
      `${id}:sphere-ring:${ringIndex}`,
      ellipsePath({
        lat,
        lon,
        altitudeM: Math.max(34, altitudeM + z * radiusM * 0.72),
        radiusXM: radiusM * f,
        radiusYM: radiusM * (0.66 + f * 0.34),
        rotationRad: angle + ringIndex * 0.32,
        segments: 14,
        scallop: 0.006,
        seed: ringIndex * 0.47 + intensity,
      }),
      rainColorForIntensity(intensity, Math.min(0.96, alpha)),
      rainColorForIntensity(intensity, 0.74),
      ringIndex === 2 ? 1.15 + intensity * 1.6 : 0.45,
      `falling precip sphere · rate ${intensity.toFixed(2)} · ${sample.id}`,
    );
    spec.altitudeMode = 'RELATIVE_TO_GROUND';
    spec.drawsOccludedSegments = true;
    spec.zIndex = 72 + ringIndex;
    specs.push(spec);
  }
  return specs;
}

function rainPolygons(samples: SamplePoint[], now = performance.now()): PolygonSpec[] {
  const specs: PolygonSpec[] = [];
  const raining = samples.filter((s) => rainIntensity(s) > 0.035).slice(0, 96);
  for (const [index, sample] of raining.entries()) {
    const intensity = rainIntensity(sample);
    const top = rainCloudTopM(sample, intensity);
    const floor = 34;
    const radius = rainFootprintM(sample, intensity, index);
    const rotation = -0.35 + index * 0.044;

    const topCap = polygonSpec(
      `rain-cloud-top:${sample.id}`,
      ellipsePath({ lat: sample.lat, lon: sample.lon, altitudeM: top, radiusXM: radius * 1.18, radiusYM: radius * 0.72, rotationRad: rotation, segments: 18, scallop: 0.018 }),
      rainColorForIntensity(intensity, 0.10 + intensity * 0.18),
      rainColorForIntensity(intensity, 0.30 + intensity * 0.16),
      0.75 + intensity * 1.05,
      `rain cloud top · precip ${intensity.toFixed(2)} · fall ${(top - floor).toFixed(0)} m`,
    );
    topCap.altitudeMode = 'RELATIVE_TO_GROUND';
    topCap.drawsOccludedSegments = true;
    topCap.zIndex = 66;
    specs.push(topCap);

    const floorSplash = polygonSpec(
      `rain-floor-splash:${sample.id}`,
      ellipsePath({ lat: sample.lat, lon: sample.lon, altitudeM: floor, radiusXM: radius * (0.30 + intensity * 0.16), radiusYM: radius * (0.18 + intensity * 0.10), rotationRad: -rotation, segments: 16, scallop: 0.012 }),
      rainColorForIntensity(intensity, 0.08 + intensity * 0.16),
      rainColorForIntensity(intensity, 0.24 + intensity * 0.15),
      0.65 + intensity * 0.75,
      `rain floor impact · precip ${intensity.toFixed(2)}`,
    );
    floorSplash.altitudeMode = 'RELATIVE_TO_GROUND';
    floorSplash.drawsOccludedSegments = true;
    floorSplash.zIndex = 58;
    specs.push(floorSplash);

    const spheres = intensity > 0.82 ? 9 : intensity > 0.66 ? 7 : intensity > 0.42 ? 5 : 3;
    for (let d = 0; d < spheres; d += 1) {
      const seed = index * 19.73 + d * 7.11;
      const phase = ((now / (1040 - Math.min(520, intensity * 420) + d * 72) + seed) % 1 + 1) % 1;
      const angle = seed * 2.399;
      const spread = (0.0022 + intensity * 0.0115) * (0.42 + d * 0.18);
      const lat = sample.lat + Math.sin(angle) * spread;
      const lon = sample.lon + Math.cos(angle) * spread;
      const altitude = Math.max(floor + 22, top - phase * (top - floor));
      const sphereRadius = 42 + intensity * 160 + (d % 3) * 11;
      specs.push(...rainSpherePolygons(sample, intensity, `rain-drop:${sample.id}:${d}`, lat, lon, altitude, sphereRadius, angle));
    }
  }
  return specs;
}

function rainDropLines(samples: SamplePoint[], now = performance.now()): PolylineSpec[] {
  const lines: PolylineSpec[] = [];
  const raining = samples.filter((s) => rainIntensity(s) > 0.035).slice(0, 90);
  for (const [index, sample] of raining.entries()) {
    const intensity = rainIntensity(sample);
    const top = rainCloudTopM(sample, intensity);
    const floor = 34;
    const drops = intensity > 0.82 ? 9 : intensity > 0.66 ? 7 : intensity > 0.42 ? 5 : 3;
    for (let d = 0; d < drops; d += 1) {
      const seed = index * 8.17 + d * 3.11;
      const phase = ((now / (900 - Math.min(460, intensity * 380) + d * 65) + seed) % 1 + 1) % 1;
      const angle = seed * 2.17;
      const spread = (0.0026 + intensity * 0.0125) * (0.48 + d * 0.22);
      const lat = sample.lat + Math.sin(angle) * spread;
      const lon = sample.lon + Math.cos(angle) * spread;
      const head = Math.max(floor + 18, top - phase * (top - floor));
      const tail = Math.min(top, head + 520 + intensity * 2250);
      lines.push({
        id: `rain-fall:${sample.id}:${d}`,
        path: [
          { lat, lng: lon, altitude: tail },
          { lat, lng: lon, altitude: head },
        ],
        strokeColor: rainColorForIntensity(intensity, 0.74),
        outerColor: rainColorForIntensity(intensity, 0.22),
        strokeWidth: 1.15 + intensity * 5.6,
        altitudeMode: 'RELATIVE_TO_GROUND',
      });
    }
  }
  return lines;
}

function waterLabelPolygons(waterbodies: SpatialFeature[]): PolygonSpec[] {
  return waterbodies.slice(0, 28).map((water) => {
    const point = water.label_point ?? { lat: water.latitude ?? 33.8, lon: water.longitude ?? -118.2 };
    return polygonSpec(
      `water-label-poly:${water.stable_id ?? water.id}`,
      ellipsePath({ lat: point.lat, lon: point.lon, altitudeM: 70, radiusXM: 620, radiusYM: 260, rotationRad: -0.18, segments: 14, scallop: 0.015 }),
      'rgba(125,211,252,.32)',
      'rgba(186,230,253,.58)',
      0.8,
      water.name ?? water.label ?? 'waterbody',
    );
  });
}

function boatPolygons(boats: BoatEntity[]): PolygonSpec[] {
  return boats.slice(0, 18).map((boat) => {
    const safetyColor = boat.safety === 'rough' ? 'rgba(248,113,113,.72)' : boat.safety === 'caution' ? 'rgba(250,204,21,.70)' : 'rgba(125,211,252,.72)';
    return polygonSpec(
      `boat-poly:${boat.id}`,
      trianglePath(boat.lat, boat.lon, 175, 900, 390, boat.heading_deg ?? 0),
      safetyColor,
      'rgba(248,250,252,.78)',
      1.6,
      `${boat.id} ${boat.safety}`,
    );
  });
}

function lightningLines(flashes: LightningFlash[]): PolylineSpec[] {
  return flashes.slice(0, 40).map((flash) => zigzagLine(`lightning-line:${flash.id}`, flash.lat, flash.lon, 650, 1900 + flash.energy * 4600, flash.energy));
}

function currentLines(patch: FieldPatch | undefined): PolylineSpec[] {
  return samplePatchGrid(patch, 42).map((sample) => {
    const u = sample.values.current_u ?? 0;
    const v = sample.values.current_v ?? 0;
    const scale = 0.045;
    return {
      id: `current:${sample.id}`,
      path: [
        { lat: sample.lat, lng: sample.lon, altitude: 120 },
        { lat: sample.lat + v * scale, lng: sample.lon + u * scale, altitude: 120 },
      ],
      strokeColor: '#22d3eecc',
      outerColor: '#00111fcc',
      strokeWidth: Math.max(2, Math.min(7, 2 + Math.hypot(u, v) * 5)),
      altitudeMode: 'RELATIVE_TO_GROUND',
    };
  });
}

async function boot(): Promise<void> {
  const mapSurface = await createGoogle3DMap();
  shell.appendChild(mapSurface.element);
  shell.append(title, renderLayerPills(activeLayers, handleLayerToggle), pane.element);
  pane.log(mapSurface.status);

  const overlay = mapSurface.overlay;
  let streamSource: EventSource | null = null;
  let currentViewportBBox: BBox | null = null;
  const streamTier: CloudTier = 'regional';
  let cachedLocations: ReportPoint[] = [];
  let cachedWaterbodies: SpatialFeature[] = [];
  let cachedHarbors: SpatialFeature[] = [];
  let lastSpatialSource = 'pending';
  let lastPostgisMode = 'pending';
  let cachedBoats: BoatEntity[] = [];
  let cachedLightning: LightningFlash[] = [];
  let cachedCloudFeatures: CloudFeaturesPayload | null = null;
  let lastCloudRenderSummary = '';
  let lastVisibleCloudParticles = 0;
  let lastVisibleCloudShapes = 0;
  const cloudMorph = new CloudMorphController();
  let cloudMorphTimer: number | null = null;
  let cachedOceanFeatures: OceanFeaturesPayload | null = null;
  let lastGoodOceanPatch: FieldPatch | undefined;
  const baitMorph = new BaitSchoolMorphController();
  let baitMorphTimer: number | null = null;
  let lastBaitRenderSummary = '';
  let lastBoatRenderSummary = '';
  let rainAnimationTimer: number | null = null;

  const groupsByLayer: Record<LayerId, string[]> = {
    locations: ['locations', 'location-models'],
    clouds: ['cloud-shapes', 'clouds'],
    rain: ['rain'],
    bait: ['bait'],
    boats: ['boat-hazards', 'boats'],
    'shark-intel': ['shark-intel'],
    'inland-water': ['waterbodies', 'water-labels'],
    lightning: ['lightning'],
  };

  function clearLayer(layer: LayerId): void {
    if (layer === 'clouds') {
      cloudMorph.clear();
      stopCloudMorphAnimation();
    }
    if (layer === 'bait') {
      baitMorph.clear();
      if (baitMorphTimer !== null) {
        window.clearInterval(baitMorphTimer);
        baitMorphTimer = null;
      }
    }
    for (const group of groupsByLayer[layer]) overlay.clearGroup(group);
  }

  function clearIfDisabled(layer: LayerId): boolean {
    if (activeLayers.has(layer)) return false;
    clearLayer(layer);
    return true;
  }

  function stopCloudMorphAnimation(): void {
    if (cloudMorphTimer !== null) {
      window.clearInterval(cloudMorphTimer);
      cloudMorphTimer = null;
    }
  }

  function syncCloudMorphFrame(): void {
    if (!activeLayers.has('clouds')) {
      clearLayer('clouds');
      return;
    }
    const frame = cloudMorph.frame({ morphSeconds: 34, holdMs: 30_000, fadeOutMs: 80_000 });
    if (frame.length) {
      overlay.syncPolygons('cloud-shapes', []);
      overlay.syncPolygons('clouds', frame);
      overlay.syncMarkers('clouds', []);
      lastVisibleCloudParticles = cloudMorph.stats.visible;
      lastVisibleCloudShapes = cloudMorph.stats.target;
    } else if (!cloudMorph.active) {
      stopCloudMorphAnimation();
    }
  }

  function ensureCloudMorphAnimation(): void {
    if (cloudMorphTimer !== null) return;
    cloudMorphTimer = window.setInterval(() => {
      if (!activeLayers.has('clouds') || !cloudMorph.active) {
        stopCloudMorphAnimation();
        return;
      }
      syncCloudMorphFrame();
    }, 420);
  }

  function updateCloudTargets(targetGeometry: PolygonSpec[], modeLabel: string): void {
    if (targetGeometry.length) {
      cloudMorph.updateTarget(targetGeometry);
      syncCloudMorphFrame();
      ensureCloudMorphAnimation();
      const stats = cloudMorph.stats;
      const summary = `Cloud persistent morph mode: ${modeLabel} → ${stats.visible} live polygons, ${stats.retained} retained/advecting, ${stats.fading} fading, 0 marker spheres`;
      if (summary !== lastCloudRenderSummary) {
        lastCloudRenderSummary = summary;
        pane.log(summary);
      }
    } else if (cloudMorph.active) {
      syncCloudMorphFrame();
      ensureCloudMorphAnimation();
      const summary = `Cloud renderer retained last good and advecting: ${lastVisibleCloudShapes} targets + ${lastVisibleCloudParticles} polygons`;
      if (summary !== lastCloudRenderSummary) {
        lastCloudRenderSummary = summary;
        pane.log(summary);
      }
    } else {
      const summary = 'Cloud renderer has no visible cloud payload yet';
      if (summary !== lastCloudRenderSummary) {
        lastCloudRenderSummary = summary;
        pane.log(summary);
      }
    }
  }

  function drawAtmosphere(): void {
    const patch = fields.latestPatch('atmosphere');
    if (!activeLayers.has('clouds')) {
      clearLayer('clouds');
    } else {
      const featureCount = cachedCloudFeatures?.features?.length ?? 0;
      const cloudShapes = featureCount ? cloudFeaturePolygons(cachedCloudFeatures, streamTier) : [];
      const fieldClouds = featureCount ? [] : cloudFamilyPolygons(patch);
      const cloudGeometry = featureCount ? cloudShapes : fieldClouds;
      updateCloudTargets(cloudGeometry, featureCount ? `${featureCount} PostGIS/GFS shell features` : 'raw atmosphere field fallback');
    }

    drawRain();
  }


  function stopRainAnimation(): void {
    if (rainAnimationTimer !== null) {
      window.clearInterval(rainAnimationTimer);
      rainAnimationTimer = null;
    }
  }

  function ensureRainAnimation(): void {
    if (rainAnimationTimer !== null) return;
    rainAnimationTimer = window.setInterval(() => {
      if (!activeLayers.has('rain')) {
        stopRainAnimation();
        return;
      }
      drawRain(performance.now());
    }, 720);
  }

  function drawRain(now = performance.now()): void {
    if (!activeLayers.has('rain')) {
      clearLayer('rain');
      stopRainAnimation();
      return;
    }
    const samples = samplePatchGrid(fields.latestPatch('atmosphere'), 60) as SamplePoint[];
    overlay.syncPolygons('rain', rainPolygons(samples, now));
    overlay.syncPolylines('rain', rainDropLines(samples, now));
    overlay.syncMarkers('rain', []);
    if (samples.some((sample) => rainIntensity(sample) > 0.035)) ensureRainAnimation();
  }

  function oceanSamplesForRender(max = 65): SamplePoint[] {
    const patch = fields.latestPatch('ocean') ?? lastGoodOceanPatch;
    const samples = samplePatchGrid(patch, max) as SamplePoint[];
    if (samples.length && patch) lastGoodOceanPatch = patch;
    return samples;
  }

  function ensureBaitAnimation(): void {
    if (baitMorphTimer !== null) return;
    baitMorphTimer = window.setInterval(() => {
      if (!activeLayers.has('bait')) {
        window.clearInterval(baitMorphTimer!);
        baitMorphTimer = null;
        return;
      }
      drawOcean(false);
    }, 840);
  }

  function drawOcean(acceptNewData = true): void {
    const samples = oceanSamplesForRender(85);
    // The Ocean pill is intentionally removed. Bait and Boats now own the ocean
    // visual space, while ocean field data still feeds bait, boats, and sharks.
    void directionGlyph;
    void currentLines;
    overlay.clearGroup('currents');
    overlay.clearGroup('current-lines');
    if (!activeLayers.has('bait')) {
      clearLayer('bait');
      return;
    }
    if (acceptNewData && (samples.length || (cachedOceanFeatures?.bait_cluster_count ?? 0) > 0)) {
      baitMorph.update(samples, cachedOceanFeatures ?? undefined);
    }
    const frame = baitMorph.frame(performance.now(), { morphSeconds: 28, holdMs: 45_000, fadeOutMs: 95_000 });
    overlay.syncPolygons('bait', frame.polygons);
    overlay.syncPolylines('bait', frame.polylines);
    overlay.syncMarkers('bait', frame.markers);
    if (frame.summary !== lastBaitRenderSummary) {
      lastBaitRenderSummary = frame.summary;
      pane.log(frame.summary);
    }
    if (frame.visibleSchools > 0) ensureBaitAnimation();
    drawSharkIntel();
  }

  function buildLocationIntelContext(report: ReportPoint): LocationIntelContext {
    const atmospherePatch = fields.latestPatch('atmosphere');
    const oceanPatch = fields.latestPatch('ocean');
    const atmosphereSample = nearestSample(samplePatchGrid(atmospherePatch, 180) as SamplePoint[], report.latitude, report.longitude);
    const oceanSample = nearestSample(samplePatchGrid(oceanPatch, 180) as SamplePoint[], report.latitude, report.longitude);
    const nearestWater = nearestFeature(cachedWaterbodies, report.latitude, report.longitude);
    const nearestHarbor = nearestFeature(cachedHarbors, report.latitude, report.longitude);
    const bboxLabel = currentViewportBBox
      ? [currentViewportBBox.west, currentViewportBBox.south, currentViewportBBox.east, currentViewportBBox.north].map((v) => v.toFixed(3)).join(',')
      : undefined;

    const oceanU = oceanSample ? valueFrom(oceanSample, ['current_u', 'u', 'water_u'], NaN) : NaN;
    const oceanV = oceanSample ? valueFrom(oceanSample, ['current_v', 'v', 'water_v'], NaN) : NaN;
    const tempC = oceanSample ? valueFrom(oceanSample, ['sst_c', 'water_temp_c', 'temperature'], NaN) : NaN;
    const baitScore = oceanSample ? valueFrom(oceanSample, ['bait_score', 'bait_probability', 'chlorophyll_score'], NaN) : NaN;

    const windU = atmosphereSample ? valueFrom(atmosphereSample, ['wind_u', 'u_wind', 'ugrd'], NaN) : NaN;
    const windV = atmosphereSample ? valueFrom(atmosphereSample, ['wind_v', 'v_wind', 'vgrd'], NaN) : NaN;
    const style = atmosphereSample ? classifyCloud(atmosphereSample) : null;
    const cloudPct = atmosphereSample ? Math.max(0, Math.min(100, valueFrom(atmosphereSample, ['cloud_density', 'total_cloud_cover', 'cloud_total'], 0) * 100)) : NaN;
    const rain = atmosphereSample ? rainIntensity(atmosphereSample) : NaN;
    const humidity = atmosphereSample ? valueFrom(atmosphereSample, ['humidity', 'relative_humidity'], NaN) : NaN;

    return {
      bboxLabel,
      spatialSource: lastSpatialSource,
      postgisMode: lastPostgisMode,
      nearestWater,
      nearestHarbor,
      ocean: oceanSample ? {
        source: (oceanPatch?.payload?.source as string | undefined) ?? oceanPatch?.tile_id,
        sampleId: oceanSample.id,
        distanceKm: oceanSample.distanceKm,
        baitScore: Number.isFinite(baitScore) ? Math.max(0, Math.min(1, baitScore)) : undefined,
        currentSpeed: Number.isFinite(oceanU) && Number.isFinite(oceanV) ? Math.hypot(oceanU, oceanV) : undefined,
        currentDirection: Number.isFinite(oceanU) && Number.isFinite(oceanV) ? compassFromVector(oceanU, oceanV) : undefined,
        currentVector: Number.isFinite(oceanU) && Number.isFinite(oceanV) ? `${oceanU.toFixed(2)}, ${oceanV.toFixed(2)}` : undefined,
        depthM: oceanSample ? valueFrom(oceanSample, ['bait_depth_m', 'depth_m'], NaN) : undefined,
        scalarZ: oceanSample ? valueFrom(oceanSample, ['depth_m', 'bait_depth_m'], NaN) : undefined,
        tempC: Number.isFinite(tempC) ? tempC : undefined,
        tempF: Number.isFinite(tempC) ? tempC * 9 / 5 + 32 : undefined,
      } : null,
      atmosphere: atmosphereSample ? {
        source: (atmospherePatch?.payload?.source as string | undefined) ?? atmospherePatch?.tile_id,
        sampleId: atmosphereSample.id,
        distanceKm: atmosphereSample.distanceKm,
        cloudPct: Number.isFinite(cloudPct) ? cloudPct : undefined,
        cloudFamily: style ? `${style.family} · ${style.renderStyle}` : undefined,
        rainIntensity: Number.isFinite(rain) ? rain : undefined,
        windSpeed: Number.isFinite(windU) && Number.isFinite(windV) ? Math.hypot(windU, windV) : undefined,
        windDirection: Number.isFinite(windU) && Number.isFinite(windV) ? compassFromVector(windU, windV) : undefined,
        humidityPct: Number.isFinite(humidity) ? Math.max(0, Math.min(100, humidity * 100)) : undefined,
        validTime: patchValidTime(atmospherePatch),
      } : null,
      counts: {
        locations: cachedLocations.length,
        waterbodies: cachedWaterbodies.length,
        harbors: cachedHarbors.length,
      },
    };
  }

  function drawLocations(reports: ReportPoint[]): void {
    cachedLocations = reports;
    pane.renderReports(reports);
    const locationsDisabled = clearIfDisabled('locations');
    if (!locationsDisabled) {
      const scale = locationOrbScaleForBBox(currentViewportBBox);
      const select = (report: ReportPoint) => pane.selectReport(report, buildLocationIntelContext(report));
      overlay.syncPolygons('locations', locationOrbPolygons(reports, select, scale));
      overlay.syncModels('location-models', []);
      // Keep the old zippy green-orb as an invisible/visible click target above the
      // polygon cylinder stack.  Google 3D polygon hit-testing is not consistent
      // across Chrome/Firefox/GPU builds, so this marker is what reliably opens
      // the fishing Location Intel pane while the real 3D orb remains underneath.
      overlay.syncMarkers('locations', locationOrbMarkers(reports, select, scale));
    }
    drawSharkIntel();
  }

  function drawWaterbodies(waterbodies: SpatialFeature[]): void {
    cachedWaterbodies = waterbodies;
    if (clearIfDisabled('inland-water')) return;
    overlay.syncPolygons('waterbodies', waterbodyPolygons(waterbodies, 24));
    overlay.syncPolygons('water-labels', waterLabelPolygons(waterbodies));
    overlay.syncMarkers('water-labels', []);
  }

  function drawBoats(boats: BoatEntity[]): void {
    cachedBoats = boats;
    if (clearIfDisabled('boats')) return;
    const oceanSamples = oceanSamplesForRender(85);
    const boatFeatures = buildMergedBoatFeatures(boats.length ? boats : cachedBoats, oceanSamples);
    const span = currentViewportBBox ? Math.max(Math.abs(currentViewportBBox.east - currentViewportBBox.west), Math.abs(currentViewportBBox.north - currentViewportBBox.south)) : 2;
    overlay.syncPolygons('boat-hazards', boatOceanHazardPolygons(oceanSamples));
    overlay.syncPolygons('boats', boatLegacyPolygons(boatFeatures));
    overlay.syncModels('boats', boatShipModels(boatFeatures, span));
    overlay.syncPolylines('boats', boatLegacyWakeLines(boatFeatures));
    overlay.syncMarkers('boats', boatLegacyMarkers(boatFeatures));
    const summary = boatLegacySummary(boatFeatures);
    if (summary !== lastBoatRenderSummary) {
      lastBoatRenderSummary = summary;
      pane.log(summary);
    }
  }

  function drawSharkIntel(): void {
    if (clearIfDisabled('shark-intel')) return;
    const oceanSamples = samplePatchGrid(fields.latestPatch('ocean'), 65) as SamplePoint[];
    overlay.syncPolygons('shark-intel', sharkIntelPolygons(cachedLocations, oceanSamples));
    overlay.syncMarkers('shark-intel', sharkIntelMarkers(cachedLocations, oceanSamples, (intel) => pane.selectSharkIntel(intel)));
  }

  function drawLightning(flashes: LightningFlash[]): void {
    cachedLightning = flashes;
    if (clearIfDisabled('lightning')) return;
    overlay.syncPolylines('lightning', lightningLines(flashes));
    overlay.syncMarkers('lightning', []);
  }

  function handleLayerToggle(layer: LayerId, isOn: boolean): void {
    if (!isOn) {
      clearLayer(layer);
      if (layer === 'rain') stopRainAnimation();
      return;
    }
    if (layer === 'locations') drawLocations(cachedLocations);
    else if (layer === 'clouds' || layer === 'rain') drawAtmosphere();
    else if (layer === 'bait') drawOcean();
    else if (layer === 'boats') drawBoats(cachedBoats);
    else if (layer === 'shark-intel') drawSharkIntel();
    else if (layer === 'inland-water') drawWaterbodies(cachedWaterbodies);
    else if (layer === 'lightning') drawLightning(cachedLightning);
  }


  function connectFieldStream(bbox: { west: number; south: number; east: number; north: number }): void {
    streamSource?.close();
    // Do not clear cached cloud features here. Keep the last PostGIS/GFS shell
    // set alive while the new settled bbox loads; the persistent cloud morph
    // reducer will advect/hold/fade old bodies until a non-empty replacement
    // arrives. This prevents the old atmosphere-field fallback swap flash.
    streamSource = openFieldStream((event) => {
      if (event.type === 'cloud.features.patch') {
        const payload = event.payload as unknown as CloudFeaturesPayload;
        if ((payload.features?.length ?? 0) > 0) {
          cachedCloudFeatures = payload;
        } else {
          pane.log('Cloud features empty on this settled swath; retaining last visible cloud field');
        }
        drawAtmosphere();
        return;
      }
      if (event.type === 'ocean.features.patch') {
        const incomingOcean = event.payload as unknown as OceanFeaturesPayload;
        if ((incomingOcean.current_vector_count ?? 0) || (incomingOcean.bait_cluster_count ?? 0)) {
          cachedOceanFeatures = incomingOcean;
          pane.log(`Ocean field engine: ${(cachedOceanFeatures.current_vector_count ?? 0)} current vectors, ${(cachedOceanFeatures.bait_cluster_count ?? 0)} bait clusters · morph/retain enabled`);
        } else {
          pane.log('Ocean features empty after land-mask/provider pass; retaining/advection-morphing last visible bait and boat hazard field');
        }
        drawOcean();
        drawBoats(cachedBoats);
        return;
      }
      if (event.type === 'atmosphere.field.patch' || event.type === 'ocean.field.patch') {
        fields.applyPatch(event.payload as unknown as FieldPatch);
        if (event.type === 'atmosphere.field.patch') drawAtmosphere();
        if (event.type === 'ocean.field.patch') {
          const patch = event.payload as unknown as FieldPatch;
          const gridShape = patch.payload?.grid_shape as unknown;
          const hasGrid = Array.isArray(gridShape) ? Number(gridShape[0]) > 0 && Number(gridShape[1]) > 0 : true;
          if (hasGrid) lastGoodOceanPatch = patch;
          drawOcean(hasGrid);
          drawBoats(cachedBoats);
        }
        return;
      }
      if (event.type === 'locations.patch' || event.type === 'reports.patch') {
        lastSpatialSource = String((event.payload as any).source ?? lastSpatialSource);
        lastPostgisMode = String((event.payload as any).postgis?.spatial_mode ?? lastPostgisMode);
        drawLocations(((event.payload.locations ?? event.payload.reports) as ReportPoint[]) ?? []);
      }
      if (event.type === 'lightning.flash') drawLightning((event.payload.flashes as LightningFlash[]) ?? []);
      if (event.type === 'boats.patch') drawBoats((event.payload.boats as BoatEntity[]) ?? []);
      if (event.type === 'stream.error') pane.log('SSE stream interrupted');
    }, { bbox, tier: streamTier });
  }

  let lastLoadedViewportKey = '';

  async function loadViewportData(bbox: BBox, reason = 'viewport'): Promise<void> {
    currentViewportBBox = bbox;
    const key = stableBBoxKey(bbox);
    const isDuplicate = key === lastLoadedViewportKey;
    if (!isDuplicate) lastLoadedViewportKey = key;
    if (cachedLocations.length) drawLocations(cachedLocations);
    const value = bboxToParam(bbox);
    try {
      const spatial = await fetchViewportSpatial(bbox);
      const waterbodies = spatial.waterbodies ?? spatial.lakes ?? [];
      cachedHarbors = (spatial.harbors ?? []) as SpatialFeature[];
      lastSpatialSource = String((spatial as any).diagnostics?.source ?? (spatial as any).spatial_mode ?? 'viewport-spatial');
      lastPostgisMode = String((spatial as any).postgis?.spatial_mode ?? (spatial as any).spatial_mode ?? 'unknown');
      const locations = (spatial.locations ?? spatial.reports ?? []) as ReportPoint[];
      // Load Locations first: green orbs are the leftmost/default layer and should appear before heavy field overlays.
      drawLocations(locations);
      drawWaterbodies(waterbodies);
      pane.log(`${reason} ${key}: ${locations.length} locations, ${waterbodies.length} waterbodies · ${lastSpatialSource}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      pane.log(`${reason} spatial error for ${key}: ${message}`);
    }

    // Always connect the SSE stream after the first bbox bootstrap.  The old code
    // waited only for Google 3D camera-settle events; on some Maps 3D builds those
    // events never fire on initial page load, leaving a beautiful empty globe with
    // pills that appear to do nothing.
    connectFieldStream(bbox);

    fetch(`/gfs/api/layers/boats?bbox=${encodeURIComponent(value)}`)
      .then((res) => res.ok ? res.json() : Promise.reject(new Error(`boats ${res.status}`)))
      .then((payload: { boats: BoatEntity[] }) => drawBoats(payload.boats ?? []))
      .catch((error: Error) => pane.log(`${reason} boats error for ${key}: ${error.message}`));
  }

  // Immediate, visible data bootstrap.  This makes the Locations pill and the
  // glass intel pane testable even if the Google 3D camera has not emitted a
  // settle/change event yet.  The viewport controller will replace this with the
  // true padded camera bbox once it becomes available.
  void loadViewportData(DEFAULT_SOCAL_BBOX, 'initial SoCal bootstrap');

  viewport.onChange((bbox) => {
    void loadViewportData(bbox, 'settled padded viewport');
  });

  viewport.attachToMap(mapSurface.element);
  window.addEventListener('resize', () => viewport.refresh());
  window.setTimeout(() => viewport.refresh(), 1200);
  window.setTimeout(() => {
    if (!cachedLocations.length) void loadViewportData(DEFAULT_SOCAL_BBOX, 'bootstrap retry');
  }, 3200);

  fetchSceneFrame().then((scene) => pane.log(`Loaded scene ${scene.scene_id}`)).catch((error: Error) => pane.log(`Scene error: ${error.message}`));
  // Field stream is opened immediately on the safe SoCal bbox, then reconnected
  // after the first settled, padded Google 3D viewport bbox is known.
}

void boot().catch((error: Error) => {
  shell.innerHTML = `<div class="map-fallback">LFTR globe failed to boot: ${error.message}</div>`;
});
