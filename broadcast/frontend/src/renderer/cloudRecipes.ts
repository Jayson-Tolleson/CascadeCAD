export type CloudFamily = 'cumulus' | 'stratus' | 'cirrus' | 'marine_stratus' | 'cumulonimbus';
export type CloudFamilyWire = CloudFamily | 'marine-stratus' | string;
export type CloudRenderStyle = 'puff_cluster' | 'flat_sheet' | 'wispy_streak' | 'coastal_blanket' | 'tower_stack';
export type CloudRenderStyleWire = CloudRenderStyle | 'puff-cluster' | 'flat-sheet' | 'wispy-streak' | 'coastal-blanket' | 'tower-stack' | string;
export type CloudSize = 'micro' | 'small' | 'medium' | 'large' | 'massive';
export type CloudTier = 'global' | 'regional' | 'local';

export interface CloudFamilyRecipe {
  family: CloudFamily;
  renderStyle: CloudRenderStyle;
  label: string;
  altitudeRangeM: [number, number];
  thicknessRangeM: [number, number];
  opacityRange: [number, number];
  toneRange: [number, number];
  shape: {
    rxRange: [number, number];
    ryRange: [number, number];
    rzRange: [number, number];
    stretchAlongWind: number;
    verticalStack: number;
    edgeSoftness: number;
    jitter: number;
  };
  budget: {
    global: [number, number];
    regional: [number, number];
    local: [number, number];
  };
}

export const CLOUD_TOTAL_PARTICLE_CAPS: Record<CloudTier, number> = {
  global: 300,
  regional: 900,
  local: 1600,
};

// Cloud Render Pass 4 recipes.  The canonical names intentionally use underscores
// for shell/generator logic while CSS and older backend payloads can still use hyphens.
export const CLOUD_FAMILY_RECIPES: Record<CloudFamily, CloudFamilyRecipe> = {
  cumulus: {
    family: 'cumulus',
    renderStyle: 'puff_cluster',
    label: '●',
    altitudeRangeM: [1600, 8200],
    thicknessRangeM: [800, 3600],
    opacityRange: [0.16, 0.40],
    toneRange: [210, 255],
    shape: { rxRange: [34, 120], ryRange: [28, 96], rzRange: [260, 1200], stretchAlongWind: 0.88, verticalStack: 0.56, edgeSoftness: 0.92, jitter: 0.50 },
    budget: { global: [8, 28], regional: [24, 96], local: [40, 160] },
  },
  stratus: {
    family: 'stratus',
    renderStyle: 'flat_sheet',
    label: '▬',
    altitudeRangeM: [900, 4600],
    thicknessRangeM: [220, 1200],
    opacityRange: [0.12, 0.30],
    toneRange: [185, 245],
    shape: { rxRange: [70, 220], ryRange: [22, 74], rzRange: [100, 420], stretchAlongWind: 1.45, verticalStack: 0.22, edgeSoftness: 1.12, jitter: 0.30 },
    budget: { global: [12, 36], regional: [34, 124], local: [70, 205] },
  },
  cirrus: {
    family: 'cirrus',
    renderStyle: 'wispy_streak',
    label: '━',
    altitudeRangeM: [7800, 13600],
    thicknessRangeM: [120, 620],
    opacityRange: [0.06, 0.18],
    toneRange: [220, 255],
    shape: { rxRange: [120, 340], ryRange: [8, 30], rzRange: [80, 340], stretchAlongWind: 2.55, verticalStack: 0.14, edgeSoftness: 1.35, jitter: 0.42 },
    budget: { global: [8, 24], regional: [24, 82], local: [40, 135] },
  },
  marine_stratus: {
    family: 'marine_stratus',
    renderStyle: 'coastal_blanket',
    label: '▬',
    altitudeRangeM: [120, 1700],
    thicknessRangeM: [120, 620],
    opacityRange: [0.16, 0.36],
    toneRange: [175, 235],
    shape: { rxRange: [90, 260], ryRange: [20, 58], rzRange: [70, 260], stretchAlongWind: 1.88, verticalStack: 0.13, edgeSoftness: 1.20, jitter: 0.24 },
    budget: { global: [14, 40], regional: [44, 140], local: [82, 220] },
  },
  cumulonimbus: {
    family: 'cumulonimbus',
    renderStyle: 'tower_stack',
    label: '●',
    altitudeRangeM: [1200, 14200],
    thicknessRangeM: [2600, 11200],
    opacityRange: [0.20, 0.58],
    toneRange: [110, 245],
    shape: { rxRange: [42, 150], ryRange: [38, 135], rzRange: [820, 4200], stretchAlongWind: 0.66, verticalStack: 1.55, edgeSoftness: 0.70, jitter: 0.58 },
    budget: { global: [16, 40], regional: [46, 140], local: [88, 220] },
  },
};

export function normalizeCloudFamily(value: CloudFamilyWire | undefined | null): CloudFamily {
  const token = String(value ?? 'cumulus').trim().toLowerCase().replace(/-/g, '_');
  if (token === 'marine_stratus') return 'marine_stratus';
  if (token === 'cumulonimbus') return 'cumulonimbus';
  if (token === 'stratus') return 'stratus';
  if (token === 'cirrus') return 'cirrus';
  return 'cumulus';
}

export function normalizeRenderStyle(value: CloudRenderStyleWire | undefined | null, family: CloudFamily): CloudRenderStyle {
  const token = String(value ?? '').trim().toLowerCase().replace(/-/g, '_');
  if (token === 'puff_cluster' || token === 'flat_sheet' || token === 'wispy_streak' || token === 'coastal_blanket' || token === 'tower_stack') return token;
  return CLOUD_FAMILY_RECIPES[family].renderStyle;
}

export function cssFamilyName(family: CloudFamily): string {
  return family.replace(/_/g, '-');
}

export function cssStyleName(style: CloudRenderStyle): string {
  return style.replace(/_/g, '-');
}

export function clamp01(value: number, fallback = 0): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(0, Math.min(1, value));
}

export function lerp(min: number, max: number, t: number): number {
  return min + (max - min) * t;
}

export function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

export function grayCss(tone: number, opacity = 1, coolBlue = 0): string {
  const g = clamp(Math.round(tone), 0, 255);
  const b = clamp(Math.round(tone + coolBlue), 0, 255);
  return `rgba(${g},${g},${b},${clamp(opacity, 0, 1).toFixed(3)})`;
}
