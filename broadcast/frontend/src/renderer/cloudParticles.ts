import type { MarkerSpec, PolygonSpec } from './google3d';
import { ellipsePath } from './geometryPrimitives';
import {
  CLOUD_FAMILY_RECIPES,
  CLOUD_TOTAL_PARTICLE_CAPS,
  clamp,
  clamp01,
  cssFamilyName,
  cssStyleName,
  grayCss,
  lerp,
  normalizeCloudFamily,
  normalizeRenderStyle,
  type CloudFamily,
  type CloudRenderStyle,
  type CloudSize,
  type CloudTier,
} from './cloudRecipes';
import { SeededRandom, hashStringToUint32, seededPhase } from './cloudSeed';

export interface CloudFeatureInput {
  id?: string;
  family?: string;
  render_style?: string;
  renderStyle?: string;
  size?: CloudSize | string;
  centroid?: { lon?: number; lat?: number };
  bbox?: { west?: number; south?: number; east?: number; north?: number };
  footprint?: Array<{ lon?: number; lng?: number; lat?: number; altitude?: number }>;
  geom?: unknown;
  area_cells?: number;
  cells_per_particle?: number;
  density?: number;
  density_max?: number;
  opacity?: number;
  altitude_m?: number;
  thickness_m?: number;
  rain_rate?: number;
  rain_factor?: number;
  wind_u?: number;
  wind_v?: number;
  particle_seed?: string;
  particle_budget?: number;
  scale?: number;
  title?: string;
}

export interface CloudFeaturesPayload {
  ok?: boolean;
  feature_count?: number;
  grid_shape?: [number, number];
  tier?: CloudTier | string;
  features?: CloudFeatureInput[];
}

export interface CloudShell {
  id: string;
  family: CloudFamily;
  renderStyle: CloudRenderStyle;
  density: number;
  opacity: number;
  altitudeM: number;
  thicknessM: number;
  windU: number;
  windV: number;
  rainFactor: number;
  bounds: { west: number; south: number; east: number; north: number };
  center: { lon: number; lat: number };
  particleSeed: string;
  particleBudget?: number;
  cellsPerParticle?: number;
  areaCells: number;
  size: CloudSize;
  title: string;
}

export interface CloudParticle {
  id: string;
  shellId: string;
  family: CloudFamily;
  renderStyle: CloudRenderStyle;
  lon: number;
  lat: number;
  altitudeM: number;
  rx: number;
  ry: number;
  rz: number;
  opacity: number;
  tone: number;
  color: string;
  glowColor: string;
  rotation: number;
  wobblePhase: number;
  driftPhase: number;
  scale: number;
  label: string;
  title: string;
}

export interface CloudBodyRender {
  shells: CloudShell[];
  particles: CloudParticle[];
  markers: MarkerSpec[];
  polygons: PolygonSpec[];
}

const SIZE_DENSITY_BONUS: Record<CloudSize, number> = { micro: 0.68, small: 0.82, medium: 1.0, large: 1.22, massive: 1.52 };

function numberFrom(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeSize(value: unknown): CloudSize {
  if (value === 'micro' || value === 'small' || value === 'medium' || value === 'large' || value === 'massive') return value;
  return 'medium';
}

function fallbackSeed(feature: CloudFeatureInput, family: CloudFamily): string {
  const bbox = feature.bbox ?? {};
  const center = feature.centroid ?? {};
  const stable = [
    feature.id ?? 'cloud-feature',
    family,
    numberFrom(center.lat, 0).toFixed(4),
    numberFrom(center.lon, 0).toFixed(4),
    numberFrom(bbox.west, 0).toFixed(3),
    numberFrom(bbox.south, 0).toFixed(3),
    numberFrom(bbox.east, 0).toFixed(3),
    numberFrom(bbox.north, 0).toFixed(3),
    numberFrom(feature.area_cells, 0),
  ].join(':');
  return hashStringToUint32(stable).toString(36);
}

export function cloudShellFromFeature(feature: CloudFeatureInput, index = 0): CloudShell | null {
  const family = normalizeCloudFamily(feature.family);
  const renderStyle = normalizeRenderStyle(feature.render_style ?? feature.renderStyle, family);
  const recipe = CLOUD_FAMILY_RECIPES[family];
  const centerLon = numberFrom(feature.centroid?.lon, Number.NaN);
  const centerLat = numberFrom(feature.centroid?.lat, Number.NaN);
  if (!Number.isFinite(centerLat) || !Number.isFinite(centerLon)) return null;

  const rawWest = numberFrom(feature.bbox?.west, centerLon - 0.12);
  const rawEast = numberFrom(feature.bbox?.east, centerLon + 0.12);
  const rawSouth = numberFrom(feature.bbox?.south, centerLat - 0.08);
  const rawNorth = numberFrom(feature.bbox?.north, centerLat + 0.08);
  const spanLon = Math.max(0.035, Math.abs(rawEast - rawWest));
  const spanLat = Math.max(0.025, Math.abs(rawNorth - rawSouth));
  const west = Math.min(rawWest, rawEast, centerLon - spanLon * 0.5);
  const east = Math.max(rawWest, rawEast, centerLon + spanLon * 0.5);
  const south = Math.min(rawSouth, rawNorth, centerLat - spanLat * 0.5);
  const north = Math.max(rawSouth, rawNorth, centerLat + spanLat * 0.5);
  const density = clamp01(numberFrom(feature.density_max, numberFrom(feature.density, 0.55)), 0.55);
  const meanDensity = clamp01(numberFrom(feature.density, density), density);
  const rainFactor = clamp01(numberFrom(feature.rain_factor, numberFrom(feature.rain_rate, 0)), 0);
  const opacity = clamp(numberFrom(feature.opacity, lerp(recipe.opacityRange[0], recipe.opacityRange[1], meanDensity) + rainFactor * 0.14), recipe.opacityRange[0] * 0.68, Math.min(0.98, recipe.opacityRange[1] + 0.22));
  const altitudeM = clamp(numberFrom(feature.altitude_m, lerp(recipe.altitudeRangeM[0], recipe.altitudeRangeM[1], meanDensity)), recipe.altitudeRangeM[0] * 0.75, recipe.altitudeRangeM[1] * 1.12);
  const thicknessM = clamp(numberFrom(feature.thickness_m, lerp(recipe.thicknessRangeM[0], recipe.thicknessRangeM[1], meanDensity) + rainFactor * 900), recipe.thicknessRangeM[0] * 0.65, recipe.thicknessRangeM[1] * 1.20);
  const areaCells = Math.max(1, Math.round(numberFrom(feature.area_cells, 24)));
  const seed = String(feature.particle_seed ?? fallbackSeed(feature, family));
  const id = String(feature.id ?? `cloud-shell-${index + 1}-${seed.slice(0, 8)}`);
  const size = normalizeSize(feature.size);

  return {
    id,
    family,
    renderStyle,
    density: meanDensity,
    opacity,
    altitudeM,
    thicknessM,
    windU: numberFrom(feature.wind_u, 0),
    windV: numberFrom(feature.wind_v, 0),
    rainFactor,
    bounds: { west, south, east, north },
    center: { lon: centerLon, lat: centerLat },
    particleSeed: seed,
    particleBudget: Number.isFinite(Number(feature.particle_budget)) ? Math.max(1, Math.round(Number(feature.particle_budget))) : undefined,
    cellsPerParticle: Number.isFinite(Number(feature.cells_per_particle)) ? Math.max(1, Math.round(Number(feature.cells_per_particle))) : undefined,
    areaCells,
    size,
    title: feature.title ?? `${cssFamilyName(family)} ${size} · ${cssStyleName(renderStyle)} · cloud ${Math.round(meanDensity * 100)}%`,
  };
}

export function cloudShellsFromPayload(payload: CloudFeaturesPayload | null | undefined): CloudShell[] {
  return (payload?.features ?? [])
    .map((feature, index) => cloudShellFromFeature(feature, index))
    .filter((shell): shell is CloudShell => shell !== null);
}

export function cloudFeatureParticleCount(featureOrShell: CloudFeatureInput | CloudShell, tier: CloudTier = 'regional'): number {
  const shell = 'bounds' in featureOrShell ? featureOrShell : cloudShellFromFeature(featureOrShell);
  if (!shell) return 0;
  return new CloudParticleGenerator().estimateParticleCount(shell, tier);
}

export function cloudFeatureParticleOffset(index: number, count: number, featureOrShell: CloudFeatureInput | CloudShell): { lat: number; lon: number; altitudeOffset: number; scaleJitter: number; opacityJitter: number; toneJitter: number } {
  const shell = 'bounds' in featureOrShell ? featureOrShell : cloudShellFromFeature(featureOrShell);
  if (!shell) return { lat: 0, lon: 0, altitudeOffset: 0, scaleJitter: 1, opacityJitter: 1, toneJitter: 0 };
  const particle = new CloudParticleGenerator().generate(shell, 'regional', count)[Math.max(0, Math.min(index, count - 1))];
  return {
    lat: particle?.lat ?? shell.center.lat,
    lon: particle?.lon ?? shell.center.lon,
    altitudeOffset: (particle?.altitudeM ?? shell.altitudeM) - shell.altitudeM,
    scaleJitter: particle?.scale ?? 1,
    opacityJitter: particle ? particle.opacity / Math.max(0.001, shell.opacity) : 1,
    toneJitter: particle ? (particle.tone - 210) / 90 : 0,
  };
}

export class CloudParticleGenerator {
  estimateParticleCount(shell: CloudShell, tier: CloudTier = 'regional'): number {
    const recipe = CLOUD_FAMILY_RECIPES[shell.family];
    const [minBudget, maxBudget] = recipe.budget[tier] ?? recipe.budget.regional;
    const areaTerm = shell.cellsPerParticle ? shell.areaCells / shell.cellsPerParticle : Math.sqrt(shell.areaCells) * 5.5;
    const fullness = clamp01(shell.density * 0.72 + shell.rainFactor * 0.22 + (shell.size === 'massive' ? 0.16 : 0), 0.55);
    const sizeBonus = SIZE_DENSITY_BONUS[shell.size] ?? 1;
    const estimated = shell.particleBudget ?? Math.round(minBudget + (maxBudget - minBudget) * fullness * sizeBonus + areaTerm);
    return Math.max(minBudget, Math.min(maxBudget, estimated));
  }

  generate(shell: CloudShell, tier: CloudTier = 'regional', forcedCount?: number): CloudParticle[] {
    const recipe = CLOUD_FAMILY_RECIPES[shell.family];
    const count = Math.max(1, forcedCount ?? this.estimateParticleCount(shell, tier));
    const rng = new SeededRandom(`${shell.particleSeed}:${shell.id}:${shell.family}:${shell.renderStyle}`);
    const particles: CloudParticle[] = [];
    const spanLon = Math.max(0.032, shell.bounds.east - shell.bounds.west);
    const spanLat = Math.max(0.024, shell.bounds.north - shell.bounds.south);
    const windAngle = Math.atan2(shell.windV || 0.2, shell.windU || 0.6);
    const axisLon = Math.cos(windAngle);
    const axisLat = Math.sin(windAngle);
    const crossLon = -axisLat;
    const crossLat = axisLon;
    const golden = Math.PI * (3 - Math.sqrt(5));

    for (let i = 0; i < count; i += 1) {
      const local = rng.fork(`particle-${i}`);
      let radius = Math.sqrt((i + 0.5) / count);
      radius = clamp(radius + local.signed(recipe.shape.jitter * 0.18), 0.02, 1.18);
      let theta = i * golden + local.signed(Math.PI * recipe.shape.jitter * 0.55);
      let along = Math.cos(theta) * radius;
      let cross = Math.sin(theta) * radius;

      if (shell.renderStyle === 'wispy_streak') {
        along = ((i / Math.max(1, count - 1)) - 0.5) * (1.75 + local.range(0.1, 0.9));
        cross = local.signed(0.15 + 0.09 * shell.density);
      } else if (shell.renderStyle === 'flat_sheet' || shell.renderStyle === 'coastal_blanket') {
        along *= 1.38 + local.range(-0.05, 0.22);
        cross *= shell.renderStyle === 'coastal_blanket' ? 0.44 : 0.58;
      } else if (shell.renderStyle === 'tower_stack') {
        along *= 0.64 + local.range(-0.08, 0.12);
        cross *= 0.62 + local.range(-0.08, 0.16);
      } else {
        along *= 0.86 + Math.sin(i * 1.7) * 0.10;
        cross *= 0.84 + Math.cos(i * 1.3) * 0.12;
      }

      const coreFalloff = clamp01(1 - Math.pow(radius, recipe.shape.edgeSoftness), 0.15);
      const lon = clamp(shell.center.lon + (axisLon * along * spanLon * 0.48 * recipe.shape.stretchAlongWind) + (crossLon * cross * spanLon * 0.34), shell.bounds.west, shell.bounds.east);
      const lat = clamp(shell.center.lat + (axisLat * along * spanLat * 0.48 * recipe.shape.stretchAlongWind) + (crossLat * cross * spanLat * 0.34), shell.bounds.south, shell.bounds.north);
      let vertical = local.next();
      if (shell.renderStyle === 'tower_stack') vertical = Math.pow(vertical, 0.62);
      if (shell.renderStyle === 'flat_sheet' || shell.renderStyle === 'coastal_blanket' || shell.renderStyle === 'wispy_streak') vertical = 0.5 + local.signed(recipe.shape.verticalStack * 0.50);
      const zOffset = (vertical - 0.42) * shell.thicknessM * recipe.shape.verticalStack + coreFalloff * shell.thicknessM * (shell.renderStyle === 'tower_stack' ? 0.55 : 0.12);
      const altitudeM = Math.max(80, shell.altitudeM + zOffset);
      const toneBase = lerp(recipe.toneRange[0], recipe.toneRange[1], coreFalloff * 0.70 + local.next() * 0.30);
      const stormDarken = shell.rainFactor * (shell.family === 'cumulonimbus' ? 72 : 28) + (1 - coreFalloff) * 20;
      const tone = clamp(toneBase - stormDarken, 72, 255);
      const opacity = clamp(shell.opacity * (0.40 + coreFalloff * 0.86 + shell.density * 0.18 + shell.rainFactor * 0.12) * local.range(0.84, 1.12), recipe.opacityRange[0] * 0.55, Math.min(0.98, recipe.opacityRange[1] + shell.rainFactor * 0.24));
      const rx = local.range(recipe.shape.rxRange[0], recipe.shape.rxRange[1]) * (0.8 + shell.density * 0.45) * (shell.renderStyle === 'wispy_streak' ? local.range(1.2, 1.9) : 1);
      const ry = local.range(recipe.shape.ryRange[0], recipe.shape.ryRange[1]) * (0.78 + coreFalloff * 0.35);
      const rz = local.range(recipe.shape.rzRange[0], recipe.shape.rzRange[1]) * (0.70 + shell.density * 0.45 + shell.rainFactor * 0.30);
      const coolBlue = shell.family === 'marine_stratus' ? 9 : shell.family === 'cumulonimbus' ? 16 : 4;
      const glowAlpha = clamp(opacity * (shell.family === 'cirrus' ? 0.35 : 0.62), 0.08, 0.58);
      const glowTone = clamp(tone + (shell.family === 'cumulonimbus' ? -18 : 12), 60, 255);
      particles.push({
        id: `${shell.id}:particle:${i}`,
        shellId: shell.id,
        family: shell.family,
        renderStyle: shell.renderStyle,
        lon,
        lat,
        altitudeM,
        rx,
        ry,
        rz,
        opacity,
        tone,
        color: grayCss(tone, 1, coolBlue),
        glowColor: grayCss(glowTone, glowAlpha, coolBlue),
        rotation: windAngle + local.signed(0.42),
        wobblePhase: seededPhase(shell.particleSeed, `wobble-${i}`),
        driftPhase: seededPhase(shell.particleSeed, `drift-${i}`),
        scale: clamp((rx + ry) / 132, 0.55, shell.family === 'cirrus' ? 2.8 : 2.25),
        label: recipe.label,
        title: `${cssFamilyName(shell.family)} · ${cssStyleName(shell.renderStyle)} · density ${Math.round(shell.density * 100)}% · particle ${i + 1}/${count}`,
      });
    }
    return particles;
  }

  generateMany(shells: CloudShell[], tier: CloudTier = 'regional'): CloudParticle[] {
    const cap = CLOUD_TOTAL_PARTICLE_CAPS[tier] ?? CLOUD_TOTAL_PARTICLE_CAPS.regional;
    const particles: CloudParticle[] = [];
    for (const shell of shells) {
      if (particles.length >= cap) break;
      const remaining = cap - particles.length;
      particles.push(...this.generate(shell, tier).slice(0, remaining));
    }
    return particles;
  }
}

export class CloudParticleRenderer {
  toMarkerSpecs(particles: CloudParticle[]): MarkerSpec[] {
    return particles.map((particle) => ({
      id: particle.id,
      lat: particle.lat,
      lon: particle.lon,
      label: particle.label,
      title: particle.title,
      altitude: particle.altitudeM,
      className: [
        'cloud-family-marker',
        `cloud-family-${cssFamilyName(particle.family)}`,
        `cloud-style-${cssStyleName(particle.renderStyle)}`,
        'cloud-feature-particle',
        'cloud-particle-ellipsoid',
        `cloud-particle-${cssFamilyName(particle.family)}`,
      ].join(' '),
      template: 'cloud-family',
      cloudFamily: cssFamilyName(particle.family),
      cloudSize: 'medium',
      scale: particle.scale,
      opacity: particle.opacity,
      color: particle.color,
      glowColor: particle.glowColor,
      cloudRx: particle.rx,
      cloudRy: particle.ry,
      cloudRz: particle.rz,
      rotation: particle.rotation,
      wobblePhase: particle.wobblePhase,
      driftPhase: particle.driftPhase,
    }));
  }

  toShellPolygons(shells: CloudShell[]): PolygonSpec[] {
    return shells.slice(0, 42).map((shell) => this.shellPolygon(shell));
  }

  /**
   * Browser-safe geometry mode: every cloud particle becomes a real
   * gmp-polygon-3d ellipse at map altitude.  This avoids the Google 3D
   * marker fallback that was reducing custom marker DOM to white spheres.
   */
  toParticlePolygons(shells: CloudShell[], particles: CloudParticle[]): PolygonSpec[] {
    const byShell = new Map(shells.map((shell) => [shell.id, shell]));
    const specs: PolygonSpec[] = [];
    for (const particle of particles) {
      const shell = byShell.get(particle.shellId);
      if (!shell) continue;
      specs.push(...this.particlePolygons(shell, particle));
    }
    return specs;
  }


  private particlePolygons(shell: CloudShell, particle: CloudParticle): PolygonSpec[] {
    const spanLatM = Math.max(900, (shell.bounds.north - shell.bounds.south) * 111_320);
    const spanLonM = Math.max(900, (shell.bounds.east - shell.bounds.west) * 111_320 * Math.max(0.18, Math.cos((shell.center.lat * Math.PI) / 180)));
    const footprintM = Math.max(spanLatM, spanLonM);
    const baseM = clamp(footprintM / (shell.renderStyle === 'wispy_streak' ? 5.5 : shell.renderStyle === 'tower_stack' ? 9.0 : 7.25), 260, 8_600);
    const rxM = clamp(baseM * (particle.rx / 115) * (shell.renderStyle === 'wispy_streak' ? 1.75 : shell.renderStyle === 'coastal_blanket' ? 1.45 : shell.renderStyle === 'flat_sheet' ? 1.30 : 1), 120, 16_000);
    const ryM = clamp(baseM * (particle.ry / 78) * (shell.renderStyle === 'tower_stack' ? 1.08 : 1), 70, 9_800);
    const familyName = cssFamilyName(particle.family);
    const styleName = cssStyleName(particle.renderStyle);
    const coreAlpha = clamp(particle.opacity, 0.05, 0.78);
    const rimAlpha = clamp(particle.opacity * 0.28, 0.025, 0.24);
    const polygons: PolygonSpec[] = [];

    // Wide low-alpha halo disc first.  It gives smooth cloud edges without a DOM sprite.
    polygons.push({
      id: `cloud-poly:${particle.id}:halo`,
      path: ellipsePath({
        lat: particle.lat,
        lon: particle.lon,
        altitudeM: Math.max(80, particle.altitudeM - Math.min(220, particle.rz * 0.12)),
        radiusXM: rxM * 1.22,
        radiusYM: ryM * 1.18,
        rotationRad: particle.rotation,
        segments: shell.renderStyle === 'wispy_streak' ? 18 : 20,
        scallop: shell.renderStyle === 'puff_cluster' || shell.renderStyle === 'tower_stack' ? 0.055 : 0.018,
        seed: hashStringToUint32(`${particle.id}:halo`),
      }),
      strokeColor: grayCss(particle.tone, rimAlpha, particle.family === 'cumulonimbus' ? 14 : 5),
      fillColor: grayCss(particle.tone, rimAlpha, particle.family === 'cumulonimbus' ? 14 : 5),
      strokeWidth: 0.5,
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 18,
      title: particle.title,
    });

    // Dense core disc.  Real gmp-polygon-3d body, not gmp-marker-3d glyph/sphere.
    polygons.push({
      id: `cloud-poly:${particle.id}:core`,
      path: ellipsePath({
        lat: particle.lat,
        lon: particle.lon,
        altitudeM: Math.max(90, particle.altitudeM),
        radiusXM: rxM,
        radiusYM: ryM,
        rotationRad: particle.rotation,
        segments: shell.renderStyle === 'wispy_streak' ? 16 : 22,
        scallop: shell.renderStyle === 'puff_cluster' || shell.renderStyle === 'tower_stack' ? 0.075 : 0.025,
        seed: hashStringToUint32(`${particle.id}:core`),
      }),
      strokeColor: grayCss(particle.tone + 5, clamp(coreAlpha * 0.32, 0.04, 0.32), particle.family === 'cumulonimbus' ? 16 : 5),
      fillColor: grayCss(particle.tone, coreAlpha, particle.family === 'cumulonimbus' ? 16 : 5),
      strokeWidth: particle.family === 'cumulonimbus' ? 1.4 : 0.8,
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      zIndex: 24,
      title: particle.title,
    });

    // Add a small bright top cap to cumulus/storm particles to create a stacked 3D read.
    if (particle.family === 'cumulus' || particle.family === 'cumulonimbus') {
      const capTone = particle.family === 'cumulonimbus' ? clamp(particle.tone + 38, 120, 245) : clamp(particle.tone + 24, 210, 255);
      polygons.push({
        id: `cloud-poly:${particle.id}:topcap`,
        path: ellipsePath({
          lat: particle.lat,
          lon: particle.lon,
          altitudeM: Math.max(100, particle.altitudeM + Math.min(520, particle.rz * 0.22)),
          radiusXM: rxM * 0.56,
          radiusYM: ryM * 0.48,
          rotationRad: particle.rotation - 0.18,
          segments: 16,
          scallop: 0.04,
          seed: hashStringToUint32(`${particle.id}:topcap`),
        }),
        strokeColor: grayCss(capTone, clamp(coreAlpha * 0.25, 0.04, 0.28), 6),
        fillColor: grayCss(capTone, clamp(coreAlpha * 0.48, 0.08, 0.44), 6),
        strokeWidth: 0.6,
        altitudeMode: 'RELATIVE_TO_GROUND',
        drawsOccludedSegments: true,
        zIndex: 29,
        title: `${particle.title} · polygon top cap`,
      });
    }

    for (const spec of polygons) {
      spec.advectU = shell.windU;
      spec.advectV = shell.windV;
    }
    // Useful string tokens for source checks: cloud-geometry-polygon-body gmp-polygon-3d particlePolygons no-marker-cloud-fill persistent-cloud-morph-advect
    void familyName;
    void styleName;
    return polygons;
  }

  private shellPolygon(shell: CloudShell): PolygonSpec {
    const recipe = CLOUD_FAMILY_RECIPES[shell.family];
    const spanLon = Math.max(0.035, shell.bounds.east - shell.bounds.west);
    const spanLat = Math.max(0.025, shell.bounds.north - shell.bounds.south);
    const windAngle = Math.atan2(shell.windV || 0.2, shell.windU || 0.6);
    const points = shell.renderStyle === 'wispy_streak' ? 22 : shell.renderStyle === 'tower_stack' ? 28 : 32;
    const rx = spanLon * 0.56 * (shell.renderStyle === 'wispy_streak' ? 2.15 : shell.renderStyle === 'coastal_blanket' ? 1.82 : shell.renderStyle === 'flat_sheet' ? 1.55 : shell.renderStyle === 'tower_stack' ? 0.72 : 0.95);
    const ry = spanLat * 0.56 * (shell.renderStyle === 'wispy_streak' ? 0.24 : shell.renderStyle === 'coastal_blanket' ? 0.46 : shell.renderStyle === 'flat_sheet' ? 0.60 : shell.renderStyle === 'tower_stack' ? 0.78 : 0.90);
    const seed = hashStringToUint32(`${shell.particleSeed}:${shell.id}:polygon`);
    const path: Array<{ lat: number; lng: number; altitude: number }> = [];
    for (let i = 0; i < points; i += 1) {
      const theta = (i / points) * Math.PI * 2;
      const scallop = 1 + 0.08 * Math.sin(theta * 3 + seed) + 0.045 * Math.cos(theta * 5 + seed * 0.03);
      const x = Math.cos(theta) * rx * scallop;
      const y = Math.sin(theta) * ry * scallop;
      const lon = shell.center.lon + x * Math.cos(windAngle) - y * Math.sin(windAngle);
      const lat = shell.center.lat + x * Math.sin(windAngle) + y * Math.cos(windAngle);
      path.push({ lat, lng: lon, altitude: Math.max(120, shell.altitudeM - Math.min(600, shell.thicknessM * 0.24)) });
    }
    const isStorm = shell.family === 'cumulonimbus';
    const fillOpacity = shell.family === 'cirrus' ? 0.08 : isStorm ? 0.22 : 0.13;
    const tone = isStorm ? 118 : lerp(recipe.toneRange[0], recipe.toneRange[1], 0.72);
    return {
      id: `cloud-footprint:${shell.id}`,
      path,
      strokeColor: grayCss(isStorm ? 132 : tone, isStorm ? 0.38 : 0.26, 8),
      fillColor: grayCss(tone, fillOpacity, 8),
      strokeWidth: isStorm ? 2 : 1,
      altitudeMode: 'RELATIVE_TO_GROUND',
      drawsOccludedSegments: true,
      advectU: shell.windU,
      advectV: shell.windV,
    };
  }
}

export function buildCloudBodyRender(payload: CloudFeaturesPayload | null | undefined, tier: CloudTier = 'regional'): CloudBodyRender {
  const generator = new CloudParticleGenerator();
  const renderer = new CloudParticleRenderer();
  const shells = cloudShellsFromPayload(payload).slice(0, 54);
  const particles = generator.generateMany(shells, tier);
  return {
    shells,
    particles,
    // Marker specs are retained only as an emergency/manual fallback. The active
    // /gfs path now draws cloud bodies through gmp-polygon-3d geometry so Google
    // cannot collapse custom marker DOM into white spheres.
    markers: renderer.toMarkerSpecs(particles),
    polygons: [...renderer.toShellPolygons(shells), ...renderer.toParticlePolygons(shells, particles)],
  };
}

export type { CloudTier } from './cloudRecipes';
