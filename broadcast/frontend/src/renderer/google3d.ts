import type { SpatialFeature } from '../types/spatial';

interface Google3DLib {
  Map3DElement: new (options: Record<string, unknown>) => HTMLElement;
  Marker3DElement?: new (options: Record<string, unknown>) => HTMLElement;
  Marker3DInteractiveElement?: new (options: Record<string, unknown>) => HTMLElement;
  Polyline3DElement?: new (options: Record<string, unknown>) => HTMLElement;
  Polygon3DElement?: new (options: Record<string, unknown>) => HTMLElement;
  Model3DElement?: new (options: Record<string, unknown>) => HTMLElement;
  AltitudeMode?: Record<string, string>;
}


declare global {
  interface Window { google?: { maps?: { importLibrary?: (name: string) => Promise<unknown> } }; }
}

export interface MapSurface {
  element: HTMLElement;
  overlay: Google3DOverlay;
  ok: boolean;
  status: string;
}

export interface MarkerSpec {
  id: string;
  lat: number;
  lon: number;
  altitude?: number;
  label?: string;
  title?: string;
  extruded?: boolean;
  className?: string;
  onClick?: () => void;
  template?: 'green-orb' | 'cloud-family';
  cloudFamily?: 'cumulus' | 'stratus' | 'cirrus' | 'marine-stratus' | 'marine_stratus' | 'cumulonimbus' | string;
  cloudSize?: 'micro' | 'small' | 'medium' | 'large' | 'massive';
  probability?: number;
  scale?: number;
  color?: string;
  glowColor?: string;
  opacity?: number;
  cloudRx?: number;
  cloudRy?: number;
  cloudRz?: number;
  rotation?: number;
  wobblePhase?: number;
  driftPhase?: number;
}



export interface PolylineSpec {
  id: string;
  path: Array<{ lat: number; lng: number; altitude?: number }>;
  strokeColor: string;
  outerColor?: string;
  strokeWidth?: number;
  altitudeMode?: string;
}

export interface ModelSpec {
  id: string;
  lat: number;
  lon: number;
  altitude?: number;
  src: string;
  scale?: number | { x: number; y: number; z: number };
  heading?: number;
  tilt?: number;
  roll?: number;
  altitudeMode?: string;
  title?: string;
  onClick?: () => void;
}

export interface PolygonSpec {
  id: string;
  path: Array<{ lat: number; lng: number; altitude?: number }>;
  strokeColor: string;
  fillColor: string;
  strokeWidth?: number;
  altitudeMode?: string;
  drawsOccludedSegments?: boolean;
  /**
   * True Google 3D polygon extrusion, not marker/sprite volume.
   * Google connects the polygon ring to the ground for ABSOLUTE/RELATIVE_TO_GROUND
   * altitude modes; it is therefore useful for terrain-anchored columns/walls,
   * but not a complete cloud/orb mesh by itself.
   */
  extruded?: boolean;
  zIndex?: number;
  title?: string;
  onClick?: () => void;
  /** Optional east/north wind in m/s used by the persistent cloud morph reducer. */
  advectU?: number;
  advectV?: number;
}


function waitForGoogleMaps(timeoutMs = 9000): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (window.google?.maps?.importLibrary) { resolve(); return; }
      if (Date.now() - start > timeoutMs) { reject(new Error('Google Maps JavaScript API did not load. Check the Maps key and maps3d library.')); return; }
      window.setTimeout(tick, 80);
    };
    tick();
  });
}

async function load3DLibrary(): Promise<Google3DLib> {
  await waitForGoogleMaps();
  const lib = await window.google!.maps!.importLibrary!('maps3d');
  return lib as Google3DLib;
}

function createFallbackMap(message: string): HTMLElement {
  const fallback = document.createElement('gmp-map-3d');
  fallback.className = 'globe-map google3d-map is-fallback';
  fallback.setAttribute('center', '33.72,-118.25,12000');
  fallback.setAttribute('tilt', '18');
  fallback.setAttribute('heading', '0');
  fallback.setAttribute('range', '115000');
  fallback.setAttribute('mode', 'HYBRID');
  const warning = document.createElement('div');
  warning.className = 'map-fallback';
  warning.textContent = message;
  fallback.appendChild(warning);
  return fallback;
}

export async function createGoogle3DMap(): Promise<MapSurface> {
  try {
    const lib = await load3DLibrary();
    const map = new lib.Map3DElement({
      center: { lat: 33.72, lng: -118.25, altitude: 12000 },
      // Zippy-style first rendering view: top-down regional weather/globe start.
      // Clouds read best here before later tilted volumetric polish.
      tilt: 18,
      heading: 0,
      range: 115000,
      mode: 'HYBRID',
      gestureHandling: 'COOPERATIVE',
    });
    map.className = 'globe-map google3d-map';
    return { element: map, overlay: new Google3DOverlay(map, lib), ok: true, status: 'Google 3D photoreal map loaded' };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Google 3D map unavailable';
    const map = createFallbackMap(message);
    return { element: map, overlay: new Google3DOverlay(map, {} as Google3DLib), ok: false, status: message };
  }
}


function greenForProbability(probability: number): { r: number; g: number; b: number } {
  if (probability >= 0.66) return { r: 57, g: 255, b: 120 };
  if (probability >= 0.33) return { r: 88, g: 245, b: 146 };
  return { r: 67, g: 217, b: 122 };
}

function ensureGreenOrb(marker: HTMLElement, spec: MarkerSpec): void {
  marker.dataset.lftrTemplate = 'green-orb';
  marker.setAttribute('data-gfs-layer', 'locations');
  marker.setAttribute('data-location-orb', 'true');
  marker.setAttribute('gmp-clickable', '');
  marker.setAttribute('interactive', '');
  marker.setAttribute('role', 'button');
  marker.tabIndex = 0;

  // Google 3D markers do not always render arbitrary HTML children in every browser build.
  // Keep a real marker glyph as the reliable old green orb, and also attach the old SVG
  // so browsers/components that support custom marker DOM show the richer legacy glow.
  const probability = Number.isFinite(spec.probability) ? Math.max(0, Math.min(1, spec.probability ?? 1)) : 1;
  const c = greenForProbability(probability);
  Object.assign(marker.style, {
    color: '#00ff55',
    filter: 'drop-shadow(0 0 14px rgba(0,255,85,1)) drop-shadow(0 0 38px rgba(0,255,85,.82))',
    textShadow: '0 0 14px rgba(0,255,85,1), 0 0 42px rgba(0,255,85,.86)',
    cursor: 'pointer',
  });
  try {
    Object.assign(marker as any, {
      label: '●',
      glyph: '●',
      scale: 2.35,
      background: `rgb(${Math.max(0, c.r - 36)}, ${c.g}, ${Math.max(0, c.b - 36)})`,
      borderColor: 'rgba(196,255,214,.92)',
      glyphColor: '#ecfff1',
    });
  } catch (_) {}
  marker.setAttribute('label', '●');
  marker.setAttribute('glyph', '●');

  if (marker.querySelector('.lftr-old-green-orb')) return;
  const uid = `lftr-orb-${Math.random().toString(36).slice(2, 10)}`;
  const tpl = document.createElement('template');
  // This is the old zippy fish-location orb pattern: a glowing SVG fragment appended
  // directly inside gmp-marker-3d-interactive, not a wrapper div that Google may ignore.
  tpl.innerHTML = `
    <svg class="lftr-old-green-orb" width="82" height="82" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="overflow:visible;pointer-events:none">
      <defs>
        <radialGradient id="${uid}-core" cx="30%" cy="28%" r="70%">
          <stop offset="0%" stop-color="#dcffe9"/>
          <stop offset="42%" stop-color="rgb(${c.r},${c.g},${c.b})"/>
          <stop offset="100%" stop-color="#003d1f"/>
        </radialGradient>
        <radialGradient id="${uid}-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgb(${c.r},${c.g},${c.b})" stop-opacity="0.68"/>
          <stop offset="100%" stop-color="rgb(${c.r},${c.g},${c.b})" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <circle data-role="halo" cx="22" cy="22" r="19" fill="url(#${uid}-halo)">
        <animate attributeName="r" values="15;22;15" dur="2.2s" repeatCount="indefinite"/>
        <animate attributeName="opacity" values="0.48;1;0.48" dur="2.2s" repeatCount="indefinite"/>
      </circle>
      <circle data-role="core" cx="22" cy="22" r="12.5" fill="url(#${uid}-core)">
        <animate attributeName="opacity" values="0.72;1;0.72" dur="1.8s" repeatCount="indefinite"/>
      </circle>
      <ellipse data-role="highlight" cx="17.5" cy="15" rx="4.5" ry="2.6" fill="white" fill-opacity="0.82" transform="rotate(-24 17.5 15)"/>
    </svg>`;
  marker.append(tpl.content);
}


function ensureCloudFamily(marker: HTMLElement, spec: MarkerSpec): void {
  const family = (spec.cloudFamily ?? 'cumulus').replace(/_/g, '-');
  const size = spec.cloudSize ?? 'medium';
  marker.dataset.lftrTemplate = 'cloud-family';
  marker.dataset.cloudFamily = family;
  marker.dataset.cloudSize = size;
  marker.classList.add('cloud-family-marker', `cloud-family-${family}`, `cloud-size-${size}`);
  marker.setAttribute('data-gfs-layer', 'clouds');
  marker.setAttribute('aria-label', spec.title ?? `${family} cloud`);

  const glyph = spec.label ?? (family === 'cirrus' ? '━' : (family === 'stratus' || family === 'marine-stratus') ? '▬' : '●');
  try {
    Object.assign(marker as any, {
      label: glyph,
      glyph,
      scale: Math.max(1.05, spec.scale ?? 1.35),
      background: 'rgba(248,251,255,.06)',
      borderColor: 'rgba(255,255,255,.10)',
      glyphColor: spec.color ?? '#ffffff',
    });
  } catch (_) {}
  marker.setAttribute('label', glyph);
  marker.setAttribute('glyph', glyph);

  const existing = marker.querySelector('.lftr-cloud-family');
  if (existing) {
    existing.setAttribute('data-family', family);
    existing.setAttribute('data-size', size);
    return;
  }

  const tpl = document.createElement('template');
  tpl.innerHTML = `
    <span class="lftr-cloud-family" data-family="${family}" data-size="${size}" aria-hidden="true">
      <span class="cloud-ellipse cloud-ellipse-a"></span>
      <span class="cloud-ellipse cloud-ellipse-b"></span>
      <span class="cloud-ellipse cloud-ellipse-c"></span>
      <span class="cloud-ellipse cloud-ellipse-d"></span>
      <span class="cloud-ellipse cloud-ellipse-shadow"></span>
    </span>`;
  marker.style.setProperty('--cloud-color', spec.color ?? '#ffffff');
  marker.style.setProperty('--cloud-glow', spec.glowColor ?? 'rgba(255,255,255,.42)');
  marker.append(tpl.content);
}

function setElementTitle(element: HTMLElement, title?: string): void {
  if (title) element.setAttribute('title', title);
}

export class Google3DOverlay {
  private readonly markers = new Map<string, HTMLElement>();
  private readonly polylines = new Map<string, HTMLElement>();
  private readonly polygons = new Map<string, HTMLElement>();
  private readonly models = new Map<string, HTMLElement>();

  constructor(private readonly map: HTMLElement, private readonly lib: Google3DLib) {}

  syncMarkers(group: string, specs: MarkerSpec[]): void {
    const keep = new Set<string>();
    for (const spec of specs) {
      if (!Number.isFinite(spec.lat) || !Number.isFinite(spec.lon)) continue;
      const key = `${group}:${spec.id}`;
      keep.add(key);
      const marker = this.markers.get(key) ?? this.createMarker(key, spec);
      this.updateMarker(marker, spec);
    }
    this.dropMissing(this.markers, group, keep);
  }

  syncPolylines(group: string, specs: PolylineSpec[]): void {
    const keep = new Set<string>();
    for (const spec of specs) {
      if (spec.path.length < 2) continue;
      const key = `${group}:${spec.id}`;
      keep.add(key);
      const line = this.polylines.get(key) ?? this.createPolyline(key);
      Object.assign(line as any, {
        path: spec.path,
        strokeColor: spec.strokeColor,
        outerColor: spec.outerColor ?? '#ffffffcc',
        strokeWidth: spec.strokeWidth ?? 4,
        altitudeMode: spec.altitudeMode ?? 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
      });
    }
    this.dropMissing(this.polylines, group, keep);
  }


  syncModels(group: string, specs: ModelSpec[]): void {
    const keep = new Set<string>();
    for (const spec of specs) {
      const key = `${group}:${spec.id}`;
      keep.add(key);
      const model = this.models.get(key) ?? this.createModel(key);
      const altitude = spec.altitude ?? 24;
      const position = { lat: spec.lat, lng: spec.lon, altitude };
      const orientation = {
        heading: spec.heading ?? 0,
        tilt: spec.tilt ?? 0,
        roll: spec.roll ?? 0,
      };
      Object.assign(model as any, {
        src: spec.src,
        position,
        orientation,
        scale: spec.scale ?? 1,
        altitudeMode: spec.altitudeMode ?? (this.lib.AltitudeMode?.RELATIVE_TO_GROUND ?? 'RELATIVE_TO_GROUND'),
        title: spec.title ?? spec.id,
      });
      model.setAttribute('src', spec.src);
      model.setAttribute('position', `${spec.lat},${spec.lon},${altitude}`);
      if (typeof spec.scale === 'number') model.setAttribute('scale', String(spec.scale));
      model.setAttribute('aria-label', spec.title ?? spec.id);
      setElementTitle(model, spec.title ?? spec.id);
      if (spec.onClick) {
        model.setAttribute('gmp-clickable', '');
        model.setAttribute('interactive', '');
        model.style.cursor = 'pointer';
      } else {
        model.removeAttribute('gmp-clickable');
        model.removeAttribute('interactive');
        model.style.cursor = '';
      }
      (model as any).__lftrClick = spec.onClick;
    }
    this.dropMissing(this.models, group, keep);
  }

  syncPolygons(group: string, specs: PolygonSpec[]): void {
    const keep = new Set<string>();
    for (const spec of specs) {
      if (spec.path.length < 3) continue;
      const key = `${group}:${spec.id}`;
      keep.add(key);
      const polygon = this.polygons.get(key) ?? this.createPolygon(key);
      Object.assign(polygon as any, {
        path: spec.path,
        strokeColor: spec.strokeColor,
        fillColor: spec.fillColor,
        strokeWidth: spec.strokeWidth ?? 2,
        altitudeMode: spec.altitudeMode ?? 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: spec.drawsOccludedSegments ?? false,
        extruded: spec.extruded ?? false,
        zIndex: spec.zIndex,
        title: spec.title ?? spec.id,
      });
      polygon.setAttribute('aria-label', spec.title ?? spec.id);
      setElementTitle(polygon, spec.title ?? spec.id);
      if (spec.onClick) {
        polygon.setAttribute('gmp-clickable', '');
        polygon.setAttribute('interactive', '');
        polygon.style.cursor = 'pointer';
      } else {
        polygon.removeAttribute('gmp-clickable');
        polygon.removeAttribute('interactive');
        polygon.style.cursor = '';
      }
      (polygon as any).__lftrClick = spec.onClick;
    }
    this.dropMissing(this.polygons, group, keep);
  }

  clearGroup(group: string): void {
    this.dropMissing(this.markers, group, new Set());
    this.dropMissing(this.polylines, group, new Set());
    this.dropMissing(this.polygons, group, new Set());
    this.dropMissing(this.models, group, new Set());
  }


  private createModel(key: string): HTMLElement {
    const Ctor = this.lib.Model3DElement;
    const model = Ctor ? new Ctor({}) : document.createElement('gmp-model-3d');
    model.dataset.lftrId = key;
    const fireClick = () => {
      const cb = (model as any).__lftrClick;
      if (typeof cb === 'function') cb();
    };
    model.addEventListener('gmp-click', fireClick);
    model.addEventListener('click', fireClick);
    this.map.append(model);
    this.models.set(key, model);
    return model;
  }

  private createMarker(key: string, spec: MarkerSpec): HTMLElement {
    const wantsInteractive = Boolean(spec.onClick || spec.template === 'green-orb' || spec.template === 'cloud-family');
    const Ctor = wantsInteractive
      ? (this.lib.Marker3DInteractiveElement ?? this.lib.Marker3DElement)
      : this.lib.Marker3DElement;
    const tag = wantsInteractive ? 'gmp-marker-3d-interactive' : 'gmp-marker-3d';
    const altitudeMode = this.lib.AltitudeMode?.RELATIVE_TO_GROUND ?? 'RELATIVE_TO_GROUND';
    const marker = Ctor ? new Ctor({
      position: { lat: 0, lng: 0, altitude: 18 },
      altitudeMode,
      drawsWhenOccluded: false,
      sizePreserved: wantsInteractive,
      extruded: false,
    }) : document.createElement(tag);
    marker.dataset.lftrId = key;
    if (wantsInteractive) {
      marker.setAttribute('gmp-clickable', '');
      marker.setAttribute('interactive', '');
      marker.setAttribute('role', 'button');
      marker.tabIndex = 0;
    }
    const fireClick = () => {
      const cb = (marker as any).__lftrClick;
      if (typeof cb === 'function') cb();
    };
    marker.addEventListener('gmp-click', fireClick);
    marker.addEventListener('click', fireClick);
    marker.addEventListener('keydown', (event: KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fireClick(); }
    });
    this.map.append(marker);
    this.markers.set(key, marker);
    return marker;
  }

  private updateMarker(marker: HTMLElement, spec: MarkerSpec): void {
    const altitude = spec.template === 'green-orb' ? (spec.altitude ?? 18) : (spec.altitude ?? 80);
    const position = { lat: spec.lat, lng: spec.lon, altitude };
    Object.assign(marker as any, {
      position,
      altitudeMode: this.lib.AltitudeMode?.RELATIVE_TO_GROUND ?? 'RELATIVE_TO_GROUND',
      drawsWhenOccluded: spec.template === 'green-orb' ? false : true,
      sizePreserved: spec.template === 'green-orb' || spec.template === 'cloud-family' ? true : undefined,
      extruded: spec.extruded ?? false,
      label: spec.template === 'green-orb' ? '●' : (spec.label ?? ''),
      title: spec.title ?? spec.label ?? spec.id,
    });
    marker.setAttribute('position', `${spec.lat},${spec.lon},${altitude}`);
    marker.className = spec.className ?? '';
    marker.style.cursor = spec.onClick ? 'pointer' : '';
    if (spec.color) {
      marker.style.color = spec.color;
      marker.style.setProperty('--cloud-color', spec.color);
    }
    if (spec.opacity !== undefined) {
      marker.style.opacity = String(Math.max(0, Math.min(1, spec.opacity)));
      marker.style.setProperty('--cloud-opacity', String(Math.max(0, Math.min(1, spec.opacity))));
    }
    const baseFontPx = spec.template === 'cloud-family' ? 42 : 22;
    if (spec.scale !== undefined) marker.style.fontSize = `${Math.max(10, Math.round(baseFontPx * spec.scale))}px`;
    if (spec.glowColor) {
      marker.style.setProperty('--cloud-glow', spec.glowColor);
      marker.style.filter = `drop-shadow(0 0 8px ${spec.glowColor}) drop-shadow(0 0 24px ${spec.glowColor})`;
      marker.style.textShadow = `0 0 10px ${spec.glowColor}, 0 0 26px ${spec.glowColor}`;
    }
    if (spec.cloudRx !== undefined) marker.style.setProperty('--cloud-rx', `${Math.max(16, spec.cloudRx).toFixed(1)}px`);
    if (spec.cloudRy !== undefined) marker.style.setProperty('--cloud-ry', `${Math.max(8, spec.cloudRy).toFixed(1)}px`);
    if (spec.cloudRz !== undefined) marker.style.setProperty('--cloud-depth-scale', String(Math.max(0.45, Math.min(2.6, spec.cloudRz / 900))));
    if (spec.rotation !== undefined) marker.style.setProperty('--cloud-rotation', `${spec.rotation.toFixed(3)}rad`);
    if (spec.wobblePhase !== undefined) marker.style.setProperty('--cloud-wobble-delay', `${(-Math.abs(spec.wobblePhase)).toFixed(3)}s`);
    if (spec.driftPhase !== undefined) marker.style.setProperty('--cloud-drift-delay', `${(-Math.abs(spec.driftPhase)).toFixed(3)}s`);
    marker.setAttribute('data-gfs-layer', (marker.dataset.lftrId ?? '').split(':', 1)[0]);
    (marker as any).__lftrClick = spec.onClick;
    if (spec.template === 'green-orb') {
      ensureGreenOrb(marker, spec);
    } else if (spec.template === 'cloud-family') {
      // Keep a real marker glyph as a browser-safe fallback; the richer DOM cloud
      // body is appended when the current Google 3D build accepts custom marker DOM.
      marker.setAttribute('label', spec.label ?? '●');
      marker.setAttribute('glyph', spec.label ?? '●');
      ensureCloudFamily(marker, spec);
    } else if (spec.label) {
      marker.setAttribute('label', spec.label);
    }
    marker.setAttribute('aria-label', spec.title ?? spec.label ?? spec.id);
    setElementTitle(marker, spec.title);
  }

  private createPolyline(key: string): HTMLElement {
    const Ctor = this.lib.Polyline3DElement;
    const line = Ctor ? new Ctor({}) : document.createElement('gmp-polyline-3d');
    line.dataset.lftrId = key;
    this.map.append(line);
    this.polylines.set(key, line);
    return line;
  }

  private createPolygon(key: string): HTMLElement {
    const Ctor = this.lib.Polygon3DElement;
    const polygon = Ctor ? new Ctor({}) : document.createElement('gmp-polygon-3d');
    polygon.dataset.lftrId = key;
    const fireClick = () => {
      const cb = (polygon as any).__lftrClick;
      if (typeof cb === 'function') cb();
    };
    polygon.addEventListener('gmp-click', fireClick);
    polygon.addEventListener('click', fireClick);
    this.map.append(polygon);
    this.polygons.set(key, polygon);
    return polygon;
  }

  private dropMissing(collection: Map<string, HTMLElement>, group: string, keep: Set<string>): void {
    for (const [key, element] of Array.from(collection)) {
      if (!key.startsWith(`${group}:`)) continue;
      if (keep.has(key)) continue;
      element.remove();
      collection.delete(key);
    }
  }
}

export function waterbodyPolygons(waterbodies: SpatialFeature[], maxCount = 24): PolygonSpec[] {
  const specs: PolygonSpec[] = [];
  for (const water of waterbodies.slice(0, maxCount)) {
    const path = firstPolygonPath(water.geometry);
    if (path.length < 3) continue;
    specs.push({
      id: water.stable_id ?? water.id,
      path,
      strokeColor: '#38bdf8cc',
      fillColor: '#0284c733',
      strokeWidth: 2,
    });
  }
  return specs;
}

function firstPolygonPath(geometry: Record<string, unknown> | undefined): Array<{ lat: number; lng: number }> {
  const type = geometry?.type;
  const coordinates = geometry?.coordinates as unknown;
  if (!Array.isArray(coordinates)) return [];
  const ring = type === 'Polygon'
    ? coordinates[0]
    : type === 'MultiPolygon'
      ? coordinates[0]?.[0]
      : undefined;
  if (!Array.isArray(ring)) return [];
  return ring
    .map((point: unknown) => Array.isArray(point) ? { lng: Number(point[0]), lat: Number(point[1]) } : undefined)
    .filter((point): point is { lat: number; lng: number } => !!point && Number.isFinite(point.lat) && Number.isFinite(point.lng));
}
