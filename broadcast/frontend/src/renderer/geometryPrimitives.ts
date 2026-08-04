import type { PolygonSpec, PolylineSpec } from './google3d';

const METERS_PER_DEGREE_LAT = 111_320;

export interface EllipseOptions {
  lat: number;
  lon: number;
  altitudeM: number;
  radiusXM: number;
  radiusYM: number;
  rotationRad?: number;
  segments?: number;
  scallop?: number;
  seed?: number;
}

function lonMetersPerDegree(lat: number): number {
  return Math.max(12_000, METERS_PER_DEGREE_LAT * Math.cos((lat * Math.PI) / 180));
}

function toLatLngOffset(lat: number, eastM: number, northM: number): { lat: number; lng: number } {
  return {
    lat: lat + northM / METERS_PER_DEGREE_LAT,
    lng: eastM / lonMetersPerDegree(lat),
  };
}

export function ellipsePath(options: EllipseOptions): Array<{ lat: number; lng: number; altitude: number }> {
  const segments = Math.max(8, Math.min(48, Math.round(options.segments ?? 18)));
  const rotation = options.rotationRad ?? 0;
  const cosR = Math.cos(rotation);
  const sinR = Math.sin(rotation);
  const scallop = Math.max(0, Math.min(0.28, options.scallop ?? 0));
  const seed = options.seed ?? 0;
  const path: Array<{ lat: number; lng: number; altitude: number }> = [];
  for (let i = 0; i < segments; i += 1) {
    const theta = (i / segments) * Math.PI * 2;
    const pulse = scallop ? 1 + scallop * Math.sin(theta * 3 + seed) + scallop * 0.55 * Math.cos(theta * 5 + seed * 0.33) : 1;
    const x = Math.cos(theta) * options.radiusXM * pulse;
    const y = Math.sin(theta) * options.radiusYM * pulse;
    const eastM = x * cosR - y * sinR;
    const northM = x * sinR + y * cosR;
    const offset = toLatLngOffset(options.lat, eastM, northM);
    path.push({ lat: offset.lat, lng: options.lon + offset.lng, altitude: options.altitudeM });
  }
  return path;
}


export function verticalEllipsePath(options: {
  lat: number;
  lon: number;
  altitudeM: number;
  radiusHorizontalM: number;
  radiusVerticalM: number;
  orientationRad?: number;
  segments?: number;
  scallop?: number;
  seed?: number;
}): Array<{ lat: number; lng: number; altitude: number }> {
  const segments = Math.max(10, Math.min(48, Math.round(options.segments ?? 20)));
  const rotation = options.orientationRad ?? 0;
  const cosR = Math.cos(rotation);
  const sinR = Math.sin(rotation);
  const scallop = Math.max(0, Math.min(0.22, options.scallop ?? 0));
  const seed = options.seed ?? 0;
  const path: Array<{ lat: number; lng: number; altitude: number }> = [];
  for (let i = 0; i < segments; i += 1) {
    const theta = (i / segments) * Math.PI * 2;
    const pulse = scallop ? 1 + scallop * Math.sin(theta * 3 + seed) + scallop * 0.45 * Math.cos(theta * 5 + seed * 0.27) : 1;
    const horizontal = Math.cos(theta) * options.radiusHorizontalM * pulse;
    const vertical = Math.sin(theta) * options.radiusVerticalM * pulse;
    const offset = toLatLngOffset(options.lat, horizontal * cosR, horizontal * sinR);
    path.push({ lat: offset.lat, lng: options.lon + offset.lng, altitude: Math.max(5, options.altitudeM + vertical) });
  }
  return path;
}

export function trianglePath(lat: number, lon: number, altitudeM: number, lengthM: number, widthM: number, headingDeg: number): Array<{ lat: number; lng: number; altitude: number }> {
  // Google headings are clockwise from north. Convert to an east/north local vector.
  const rad = ((90 - headingDeg) * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const forward = { east: cos * lengthM * 0.62, north: sin * lengthM * 0.62 };
  const back = { east: -cos * lengthM * 0.38, north: -sin * lengthM * 0.38 };
  const perp = { east: -sin * widthM * 0.5, north: cos * widthM * 0.5 };
  const pts = [
    forward,
    { east: back.east + perp.east, north: back.north + perp.north },
    { east: back.east - perp.east, north: back.north - perp.north },
  ];
  return pts.map((pt) => {
    const offset = toLatLngOffset(lat, pt.east, pt.north);
    return { lat: offset.lat, lng: lon + offset.lng, altitude: altitudeM };
  });
}

export function zigzagLine(id: string, lat: number, lon: number, altitudeM: number, heightM: number, energy: number): PolylineSpec {
  const widthM = 85 + energy * 220;
  const steps = 6;
  const path: Array<{ lat: number; lng: number; altitude: number }> = [];
  for (let i = 0; i < steps; i += 1) {
    const t = i / Math.max(1, steps - 1);
    const eastM = (i % 2 === 0 ? -1 : 1) * widthM * (0.25 + t * 0.22);
    const northM = (0.5 - t) * widthM * 1.35;
    const offset = toLatLngOffset(lat, eastM, northM);
    path.push({ lat: offset.lat, lng: lon + offset.lng, altitude: altitudeM + (1 - t) * heightM });
  }
  return {
    id,
    path,
    strokeColor: energy > 0.65 ? 'rgba(255,255,255,.94)' : 'rgba(253,224,71,.88)',
    outerColor: 'rgba(250,204,21,.48)',
    strokeWidth: Math.max(3, Math.min(9, 3 + energy * 7)),
    altitudeMode: 'RELATIVE_TO_GROUND',
  };
}

export function layeredOrbPolygons(options: {
  id: string;
  lat: number;
  lon: number;
  altitudeM: number;
  radiusM: number;
  fillColor: string;
  coreColor: string;
  strokeColor: string;
  title?: string;
  onClick?: () => void;
}): PolygonSpec[] {
  const horizontalLayers = [
    { suffix: 'halo-low', altitude: options.altitudeM - 8, radius: options.radiusM * 1.34, fill: options.fillColor, stroke: 'rgba(110,255,170,.30)', width: 1 },
    { suffix: 'core', altitude: options.altitudeM, radius: options.radiusM, fill: options.coreColor, stroke: options.strokeColor, width: 2 },
    { suffix: 'highlight', altitude: options.altitudeM + options.radiusM * 0.34, radius: options.radiusM * 0.46, fill: 'rgba(238,255,244,.74)', stroke: 'rgba(255,255,255,.40)', width: 1 },
  ];
  const horizontal: PolygonSpec[] = horizontalLayers.map((layer, index) => ({
    id: `${options.id}:${layer.suffix}`,
    path: ellipsePath({ lat: options.lat, lon: options.lon, altitudeM: Math.max(5, layer.altitude), radiusXM: layer.radius, radiusYM: layer.radius * (index === 2 ? 0.62 : 1), rotationRad: -0.42, segments: 22, scallop: index === 1 ? 0.035 : 0 }),
    strokeColor: layer.stroke,
    fillColor: layer.fill,
    strokeWidth: layer.width,
    altitudeMode: 'RELATIVE_TO_GROUND',
    drawsOccludedSegments: true,
    zIndex: 40 + index,
    title: options.title,
    onClick: index === 1 ? options.onClick : undefined,
  }));
  const vertical: PolygonSpec[] = [0, Math.PI / 2].map((orientation, index) => ({
    id: `${options.id}:vertical-${index}`,
    path: verticalEllipsePath({
      lat: options.lat,
      lon: options.lon,
      altitudeM: options.altitudeM + options.radiusM * 0.38,
      radiusHorizontalM: options.radiusM * 0.72,
      radiusVerticalM: options.radiusM * 0.58,
      orientationRad: orientation,
      segments: 22,
      scallop: 0.025,
      seed: index * 1.77,
    }),
    strokeColor: index === 0 ? 'rgba(190,255,216,.58)' : 'rgba(110,255,170,.42)',
    fillColor: index === 0 ? 'rgba(26,255,118,.26)' : 'rgba(26,255,118,.18)',
    strokeWidth: 1,
    altitudeMode: 'RELATIVE_TO_GROUND',
    drawsOccludedSegments: true,
    zIndex: 44 + index,
    title: options.title,
  }));
  return [...horizontal, ...vertical];
}

export function polygonSpec(id: string, path: Array<{ lat: number; lng: number; altitude: number }>, fillColor: string, strokeColor: string, strokeWidth = 1, title?: string): PolygonSpec {
  return {
    id,
    path,
    fillColor,
    strokeColor,
    strokeWidth,
    altitudeMode: 'RELATIVE_TO_GROUND',
    drawsOccludedSegments: true,
    title,
  };
}
