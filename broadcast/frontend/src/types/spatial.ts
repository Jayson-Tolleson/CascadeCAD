import type { BBox } from './field';

export interface ReportPoint {
  id: string;
  kind: 'report';
  title: string;
  latitude: number;
  longitude: number;
  observed_at: string;
  summary: string;
  source: string;
  csv_fields?: Record<string, string>;
  report_indices?: string[];
  marine_mask?: {
    should_render_ocean?: boolean;
    is_water?: boolean;
    classification?: string;
    reason?: string;
    matched_water?: string;
    matched_land?: string;
  };
}

export interface SpatialFeature {
  id: string;
  stable_id?: string;
  kind: string;
  label?: string;
  name?: string;
  source?: string;
  area_km2?: number;
  label_point?: { lon: number; lat: number };
  bbox?: number[];
  geometry?: Record<string, unknown>;
  latitude?: number | null;
  longitude?: number | null;
  metadata?: Record<string, unknown>;
  properties?: Record<string, unknown>;
}

export interface ViewportSpatialResponse {
  ok: boolean;
  bbox: BBox;
  tier: string;
  geometry_tier?: string;
  spatial_mode?: string;
  reports: ReportPoint[];
  locations?: ReportPoint[];
  lakes: SpatialFeature[];
  waterbodies: SpatialFeature[];
  harbors: SpatialFeature[];
  coast_mask: Record<string, unknown>;
  postgis: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
}
