import type { BBox } from '../types/field';

type ViewportListener = (bbox: BBox) => void;

interface ViewportPaddingOptions {
  /** Base padding around the estimated visible camera footprint. */
  basePaddingRatio?: number;
  /** Minimum half-height of a regional request, in meters. */
  minHalfHeightMeters?: number;
  /** Safety cap: never let a settled request become a global/weather-all bbox. */
  maxLatSpanDeg?: number;
  /** Safety cap: keep frontend/backend field math in a non-dateline-crossing regional swath. */
  maxLonSpanDeg?: number;
}

interface CameraSnapshot {
  lat: number;
  lon: number;
  rangeMeters: number;
  tiltDeg: number;
  widthPx: number;
  heightPx: number;
}

function finiteNumber(value: unknown, fallback: number): number {
  const numeric = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeLon(lon: number): number {
  let value = lon;
  while (value < -180) value += 360;
  while (value > 180) value -= 360;
  return value;
}

function isFiniteBBox(bbox: BBox): boolean {
  return [bbox.west, bbox.south, bbox.east, bbox.north].every(Number.isFinite);
}

function isSaneRegionalBBox(bbox: BBox, options: Required<ViewportPaddingOptions>): boolean {
  if (!isFiniteBBox(bbox)) return false;
  if (bbox.north <= bbox.south || bbox.east <= bbox.west) return false;
  const latSpan = bbox.north - bbox.south;
  const lonSpan = bbox.east - bbox.west;
  // If the camera briefly reports a globe-scale range while the user is moving,
  // do not reconnect the data stream to a massive/world-crossing box. That was
  // the cause of blank cloud redraws after settle.
  return latSpan > 0.05 && lonSpan > 0.05 && latSpan <= options.maxLatSpanDeg && lonSpan <= options.maxLonSpanDeg;
}

function readMapCenter(map: HTMLElement): { lat: number; lon: number } {
  const raw = (map as any).center;
  if (raw && typeof raw === 'object') {
    const lat = finiteNumber(raw.lat ?? raw.latitude, 33.72);
    const lon = finiteNumber(raw.lng ?? raw.lon ?? raw.longitude, -118.25);
    return { lat, lon };
  }
  const attr = map.getAttribute('center') ?? '';
  const [latRaw, lonRaw] = attr.split(',');
  return { lat: finiteNumber(latRaw, 33.72), lon: finiteNumber(lonRaw, -118.25) };
}

function readCameraSnapshot(map: HTMLElement): CameraSnapshot {
  const center = readMapCenter(map);
  const rangeMeters = Math.max(18000, finiteNumber((map as any).range ?? map.getAttribute('range'), 115000));
  const tiltDeg = clamp(finiteNumber((map as any).tilt ?? map.getAttribute('tilt'), 18), 0, 75);
  const rect = map.getBoundingClientRect();
  return {
    lat: center.lat,
    lon: center.lon,
    rangeMeters,
    tiltDeg,
    widthPx: Math.max(320, Math.round(rect.width || window.innerWidth || 1270)),
    heightPx: Math.max(320, Math.round(rect.height || window.innerHeight || 768)),
  };
}

function bboxKey(bbox: BBox): string {
  // 3 decimals is about 100m latitude precision: enough to prevent duplicate stream
  // reconnects while still detecting real pan/zoom swath changes.
  return [bbox.west, bbox.south, bbox.east, bbox.north].map((v) => v.toFixed(3)).join(',');
}

function resolutionPaddingRatio(widthPx: number, heightPx: number): number {
  const shortSide = Math.min(widthPx, heightPx);
  const aspect = widthPx / Math.max(1, heightPx);
  // Extra padding for 1270x768 laptop-ish views and smaller tablets/phones; a
  // little less for 1080p/large desktops. This keeps cloud/rain/ocean swaths from
  // popping at the screen edge when users pan or zoom before the next settle fetch.
  const shortSidePad = shortSide <= 768 ? 0.28 : shortSide <= 900 ? 0.23 : shortSide <= 1080 ? 0.17 : 0.12;
  const aspectPad = clamp(Math.abs(aspect - 1) * 0.09, 0, 0.16);
  return shortSidePad + aspectPad;
}

function cameraSnapshotToPaddedBBox(snapshot: CameraSnapshot, options: Required<ViewportPaddingOptions>): BBox {
  const aspect = snapshot.widthPx / Math.max(1, snapshot.heightPx);
  // Map3DElement range is camera distance to target. We request a generous field
  // swath because weather/ocean fields need off-screen data for interpolation and
  // drift, not just the exact visible pixels. But the stream/render stack is a
  // regional field renderer, not a global dateline-crossing renderer yet, so cap
  // request size aggressively enough to avoid accidental whole-earth swaths.
  const tiltBoost = 1 + (snapshot.tiltDeg / 90) * 0.42;
  const halfHeightMeters = Math.max(options.minHalfHeightMeters, snapshot.rangeMeters * 1.48 * tiltBoost);
  const halfWidthMeters = halfHeightMeters * clamp(aspect, 0.62, 2.35);
  const padRatio = clamp(options.basePaddingRatio + resolutionPaddingRatio(snapshot.widthPx, snapshot.heightPx), 0.38, 0.82);
  const paddedHalfHeight = halfHeightMeters * (1 + padRatio);
  const paddedHalfWidth = halfWidthMeters * (1 + padRatio);

  const metersPerDegreeLat = 111_320;
  const metersPerDegreeLon = Math.max(18_000, 111_320 * Math.cos((snapshot.lat * Math.PI) / 180));
  const dLat = Math.min(options.maxLatSpanDeg / 2, paddedHalfHeight / metersPerDegreeLat);
  const unclampedDLon = paddedHalfWidth / metersPerDegreeLon;
  const centerLon = normalizeLon(snapshot.lon);
  // Keep the request non-dateline-crossing until we add explicit dateline split
  // tiles. This prevents west>east boxes like 166,...,-40,... that broke cloud
  // clamps and erased swaths.
  const datelineSafeHalfLon = Math.max(0.35, (179.25 - Math.abs(centerLon)) * 0.96);
  const dLon = Math.min(options.maxLonSpanDeg / 2, datelineSafeHalfLon, unclampedDLon);
  const centerLat = clamp(snapshot.lat, -78, 78);

  return {
    west: normalizeLon(centerLon - dLon),
    south: clamp(centerLat - dLat, -84.5, 84.5),
    east: normalizeLon(centerLon + dLon),
    north: clamp(centerLat + dLat, -84.5, 84.5),
  };
}

export class ViewportController {
  private timer: number | undefined;
  private listeners = new Set<ViewportListener>();
  private mapElement: HTMLElement | null = null;
  private lastKey = '';
  private lastGoodBBox: BBox = { west: -125.0, south: 32.0, east: -117.0, north: 38.0 };
  private readonly options: Required<ViewportPaddingOptions>;

  constructor(private readonly debounceMs = 650, options: ViewportPaddingOptions = {}) {
    this.options = {
      basePaddingRatio: options.basePaddingRatio ?? 0.28,
      minHalfHeightMeters: options.minHalfHeightMeters ?? 185_000,
      maxLatSpanDeg: options.maxLatSpanDeg ?? 24,
      maxLonSpanDeg: options.maxLonSpanDeg ?? 36,
    };
  }

  onChange(listener: ViewportListener): void { this.listeners.add(listener); }

  attachToMap(map: HTMLElement): void {
    this.mapElement = map;
    const schedule = () => this.scheduleFromMap();
    for (const eventName of [
      'gmp-centerchange', 'gmp-rangechange', 'gmp-tiltchange', 'gmp-headingchange',
      'gmp-camerachange', 'camera_changed', 'bounds_changed', 'wheel', 'pointerup',
      'touchend', 'keyup',
    ]) {
      map.addEventListener(eventName, schedule, { passive: true } as AddEventListenerOptions);
    }
    this.scheduleFromMap();
  }

  refresh(): void { this.scheduleFromMap(); }

  /** Fallback used only if Google 3D camera data is unavailable. */
  updateFromMockCamera(): void {
    this.scheduleEmit({ west: -125.0, south: 32.0, east: -117.0, north: 38.0 });
  }

  private scheduleFromMap(): void {
    if (!this.mapElement) { this.updateFromMockCamera(); return; }
    const snapshot = readCameraSnapshot(this.mapElement);
    const candidate = cameraSnapshotToPaddedBBox(snapshot, this.options);
    if (!isSaneRegionalBBox(candidate, this.options)) {
      // Google 3D can report transient globe-scale camera values during gesture
      // movement. Keep the last sane swath instead of reconnecting the stream to
      // a huge/inverted bbox that makes clouds disappear.
      this.scheduleEmit(this.lastGoodBBox);
      return;
    }
    this.lastGoodBBox = candidate;
    this.scheduleEmit(candidate);
  }

  private scheduleEmit(bbox: BBox): void {
    window.clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.emitIfChanged(bbox), this.debounceMs);
  }

  private emitIfChanged(bbox: BBox): void {
    const key = bboxKey(bbox);
    if (key === this.lastKey) return;
    this.lastKey = key;
    for (const listener of this.listeners) listener(bbox);
  }
}
