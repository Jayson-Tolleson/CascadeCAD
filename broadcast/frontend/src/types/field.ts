export interface FieldPatch { patch_id: string; field_type: 'atmosphere' | 'ocean'; tile_id: string; bbox: BBox; lod: number; channels: string[]; encoding: 'json-grid'; payload: Record<string, unknown>; }
export interface AtmosphereFieldFrame { bbox: BBox; valid_time: string; grid_shape: [number, number]; levels: string[]; channels: Record<'cloud_density' | 'rain_rate' | 'wind_u' | 'wind_v' | 'humidity', number[][]>; }
export interface OceanFieldFrame { bbox: BBox; valid_time: string; grid_shape: [number, number]; depth_levels: string[]; channels: Record<'sst_c' | 'current_u' | 'current_v' | 'bait_score', number[][]>; }
export interface BBox { west: number; south: number; east: number; north: number; }
